'use strict';
const path = require('node:path');
const fs = require('node:fs');
const repoRoot = path.resolve(__dirname, '..');
const resolveRepo = value => path.resolve(repoRoot, value);
const wslPath = file => file.replaceAll('\\', '/').replace(/^([A-Za-z]):/, (_, drive) => '/mnt/' + drive.toLowerCase());

// A JSON argv array supports WSL without invoking a command shell.
function pythonCommand(script, args = []) {
  const configured = process.env.ECE191_PYTHON;
  const local = path.join(repoRoot, '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');
  const command = configured ? (configured.trim().startsWith('[') ? JSON.parse(configured) : [configured])
    : [fs.existsSync(local) ? local : process.platform === 'win32' ? 'python' : 'python3'];
  if (!Array.isArray(command) || !command.length || !command.every(x => typeof x === 'string' && x.length)) {
    throw Error('ECE191_PYTHON must be an executable path or a JSON argv array');
  }
  const env = {...process.env, PYTHONIOENCODING: 'utf-8', PYTHONDONTWRITEBYTECODE: '1'};
  const isWsl = /(^|[\\/])wsl(?:\.exe)?$/i.test(command[0]);
  if (!isWsl) return {file: command[0], args: [...command.slice(1), '-B', script, ...args], env};
  const boundary = command.indexOf('--exec');
  if (boundary < 0 || !command[boundary + 1]) throw Error('WSL configuration requires --exec followed by Python');
  const names = ['ECE191_DATA_ROOT', 'ECE191_MAP_PATH', 'ECE191_SCENES_ROOT', 'DEMO_TRACE_ROOT', 'ECE191_PARSER_PROMPT'];
  const values = names.filter(name => env[name]).map(name => {
    const base = name === 'ECE191_MAP_PATH' ? resolveRepo(env.ECE191_DATA_ROOT || '.') : repoRoot;
    const value = env[name].startsWith('/') ? env[name] : wslPath(path.resolve(base, env[name]));
    return `${name}=${value}`;
  });
  for (const name of ['ECE191_CODEX', 'ECE191_CLAUDE', 'ECE191_GEMINI', 'ECE191_AGY']) {
    if (env[name]) values.push(`${name}=${wslPath(env[name])}`);
  }
  return {file: command[0], args: [...command.slice(1, boundary + 1), 'env',
    'PYTHONDONTWRITEBYTECODE=1', 'PYTHONIOENCODING=utf-8', ...values,
    ...command.slice(boundary + 1), '-B', wslPath(script), ...args], env};
}
module.exports = {repoRoot, resolveRepo, wslPath, pythonCommand};
