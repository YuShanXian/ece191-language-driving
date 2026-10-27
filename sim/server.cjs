'use strict';
const http = require('node:http');
const fs = require('node:fs');
const fsp = require('node:fs/promises');
const path = require('node:path');
const crypto = require('node:crypto');
const {
  execFile
} = require('node:child_process');
const {
  promisify
} = require('node:util');
const {
  PlannerWorker
} = require('./worker-client.cjs');
const {repoRoot: root, resolveRepo, pythonCommand} = require('./runtime.cjs');
const port = Number(process.env.DEMO_PORT || 8775);
const logRoot = resolveRepo(process.env.DEMO_TRACE_ROOT || 'logs');
fs.mkdirSync(path.join(logRoot, 'requests'), {
  recursive: true
});
const worker = new PlannerWorker();
const json = (res, status, data) => {
  res.writeHead(status, {
    'Content-Type': 'application/json; charset=utf-8',
    'Cache-Control': 'no-store'
  });
  res.end(JSON.stringify(data));
};
const catalog = () => JSON.parse(fs.readFileSync(path.join(__dirname, 'parser/demo-models.json'), 'utf8').replace(/^\uFEFF/, ''));
const journal = event => fsp.appendFile(path.join(logRoot, 'events.jsonl'), JSON.stringify({
  time: new Date().toISOString(),
  ...event
}) + '\n').catch(console.error);
const body = async req => {
  let text = '';
  for await (const chunk of req) {
    text += chunk;
    if (text.length > 2000000) throw Error('Request too large');
  }
  return JSON.parse(text);
};
const reviewApi=require('./review-api.cjs').createReviewApi({dataRoot:resolveRepo(process.env.ECE191_REVIEW_DATA_ROOT || 'sim/review-data'),reviewRoot:resolveRepo(process.env.ECE191_REVIEW_ROOT || 'logs/reviews'),json,body});
const allowedFiles = new Set(['index.html', 'app.js', 'motion.js', 'motion-status.js', 'stop-status.js', 'clock.js', 'pipeline.js', 'view.js', 'style.css','review.html','review.css','review.js','review-core.js']);

let parsing = false;
const server = http.createServer(async (req, res) => {
  const started = performance.now(),
    id = crypto.randomUUID();
  try {
    const url = new URL(req.url, 'http://localhost');
    if(await reviewApi(req,res,url))return;
    if (req.method === 'GET') {
      if (url.pathname === '/health') return json(res, 200, {
        service: require('./package.json').name,
        release: 'v40',
        version: require('./package.json').version,
        status: 'ok',
        pid: process.pid,
        uptime_seconds: Math.round(process.uptime()),
        planner: worker.status()
      });
      if (url.pathname === '/api/models') return json(res, 200, catalog());
      if (url.pathname === '/api/scene') return json(res, 200, await worker.request({
        op: 'scene',
        scene: Number(url.searchParams.get('scene'))
      }));
      if (url.pathname === '/api/history') {
        const text = await fsp.readFile(path.join(logRoot, 'events.jsonl'), 'utf8').catch(() => '');
        return json(res, 200, text.trim().split('\n').filter(Boolean).slice(-100).map(x => JSON.parse(x)).reverse());
      }
      const file = url.pathname === '/' ? 'index.html' : ['/review','/review/'].includes(url.pathname)?'review.html':url.pathname.slice(1);
      if (!allowedFiles.has(file)) return json(res, 404, {
        error: 'Not found'
      });
      const data = await fsp.readFile(path.join(__dirname, 'web', file));
      res.writeHead(200, {
        'Content-Type': file.endsWith('.js') ? 'text/javascript' : file.endsWith('.css') ? 'text/css' : 'text/html; charset=utf-8',
        'Cache-Control': 'no-store'
      });
      return res.end(data);
    }
    if (req.method !== 'POST') return json(res, 405, {
      error: 'Method not allowed'
    });
    const input = await body(req);
    if (url.pathname === '/api/events') {
      await journal({
        type: 'browser',
        ...input
      });
      return json(res, 200, {
        ok: true
      });
    }
    if (url.pathname === '/api/plan') {
      if (!Number.isInteger(input.scene) || input.scene < 1 || input.scene > 7 || !Array.isArray(input.state?.xy) || input.state.xy.length !== 2 || ![...input.state.xy, input.state.heading, input.state.speed].every(Number.isFinite)) return json(res, 400, {
        error: 'Invalid scene or pose'
      });
      const result = await worker.request({
        ...input,
        op: input.op === 'follow' ? 'follow' : 'plan'
      });
      const elapsed_ms = +(performance.now() - started).toFixed(2);
      await fsp.writeFile(path.join(logRoot, 'requests', id + '.json'), JSON.stringify({
        id,
        time: new Date().toISOString(),
        elapsed_ms,
        request: input,
        result
      }));
      await journal({
        type: 'plan',
        id,
        scene: input.scene,
        action: input.stage?.action,
        status: result.status,
        elapsed_ms,
        origin: input.state.xy,
        node_id: input.state.node_id
      });
      return json(res, 200, {
        ...result,
        request_id: id,
        elapsed_ms
      });
    }
    if (url.pathname === '/api/parse') {
      const models = catalog(),
        model = input.model || models.default;
      if (typeof input.instruction !== 'string' || !input.instruction.trim() || input.instruction.length > 1000 || !models.models.some(m => m.id === model && m.enabled)) return json(res, 400, {
        error: 'Invalid instruction or model'
      });
      if (parsing) return json(res, 409, {
        error: 'A language request is already being parsed'
      });
      parsing = true;
      try {
        const command = pythonCommand(path.join(__dirname, 'parser/parser_backends.py'), ['--model', model, '--instruction', input.instruction]);
        const {
          stdout
        } = await promisify(execFile)(command.file, command.args, {
          timeout: 180000,
          maxBuffer: 8 * 1024 * 1024,
          windowsHide: true,
          env: command.env,
          cwd: root
        });
        const parsed = await worker.request({
          op: 'normalize',
          plan: JSON.parse(stdout)
        });
        await journal({
          type: 'parse',
          instruction: input.instruction,
          model,
          result: parsed,
          elapsed_ms: performance.now() - started
        });
        return json(res, 200, parsed);
      } finally {
        parsing = false;
      }
    }
    return json(res, 404, {
      error: 'Not found'
    });
  } catch (error) {
    await journal({
      type: 'error',
      id,
      error: error.message,
      url: req.url
    });
    const publicError = req.url === '/api/parse' ? (/usage limit reached|usage_limit_reached/i.test(error.message) ? 'The selected model has reached its usage limit. Choose another configured model and retry.' : 'Language parsing failed. Retry this step; full details are saved in diagnostics.') : error.message;
    json(res, 500, {
      error: publicError,
      request_id: id
    });
  }
});
server.listen(port, '127.0.0.1', () => console.log(`Language-guided driving: http://localhost:${port}`));
process.on('exit', () => worker.close());
for (const signal of ['SIGTERM', 'SIGINT']) process.on(signal, () => {
  worker.close();
  server.close(() => process.exit(0));
});
