'use strict';
const {
  spawn
} = require('node:child_process');
const path = require('node:path');

const {pythonCommand, repoRoot, wslPath} = require('./runtime.cjs');

class PlannerWorker {
  constructor({
    script = path.join(__dirname, 'worker.py'),
    onError = console.error
  } = {}) {
    this.script = script;
    this.onError = onError;
    this.process = null;
    this.pending = new Map();
    this.sequence = 0;
  }
  start() {
    if (this.process) return this.process;
    const command = pythonCommand(this.script);
    const child = spawn(command.file, command.args, {
      cwd: repoRoot,
      env: {...command.env, PYTHONUNBUFFERED: '1'},
      windowsHide: true,
      stdio: ['pipe', 'pipe', 'pipe']
    });
    this.process = child;
    let buffer = '',
      closed = false;
    const fail = error => {
      if (closed) return;
      closed = true;
      if (this.process === child) this.process = null;
      for (const [id, item] of this.pending)
        if (item.child === child) {
          clearTimeout(item.timer);
          item.reject(error);
          this.pending.delete(id);
        }
    };
    child.stdout.setEncoding('utf8');
    child.stdout.on('data', chunk => {
      buffer += chunk;
      let end;
      while ((end = buffer.indexOf('\n')) >= 0) {
        const line = buffer.slice(0, end);
        buffer = buffer.slice(end + 1);
        try {
          const message = JSON.parse(line),
            item = this.pending.get(message.id);
          if (!item || item.child !== child) continue;
          this.pending.delete(message.id);
          clearTimeout(item.timer);
          if (message.error) item.reject(new Error(message.error));
          else item.resolve({
            ...message.result,
            worker_ms: message.elapsed_ms
          });
        } catch (error) {
          this.onError('Invalid planner reply: ' + error.message);
        }
      }
    });
    child.stderr.on('data', chunk => this.onError(String(chunk)));
    child.on('error', fail);
    child.stdin.on('error', fail);
    child.on('exit', code => fail(new Error('Planner exited: ' + code)));
    return child;
  }
  request(payload) {
    if (this.pending.size >= 16) return Promise.reject(new Error('Planner queue is busy; try again shortly'));
    const child = this.start(),
      id = ++this.sequence;
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        if (this.pending.has(id)) child.kill();
      }, 60000);
      this.pending.set(id, {
        resolve,
        reject,
        timer,
        child
      });
      child.stdin.write(JSON.stringify({
        ...payload,
        id
      }) + '\n', error => {
        if (error) {
          clearTimeout(timer);
          this.pending.delete(id);
          reject(error);
        }
      });
    });
  }
  close() {
    this.process?.kill();
  }
  status() {
    return {
      running: !!this.process,
      pending: this.pending.size
    };
  }
}
module.exports = {
  PlannerWorker,
  wslPath
};
