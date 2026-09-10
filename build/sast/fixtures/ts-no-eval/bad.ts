// SAST canary fixture — ts-no-eval. Never bundled/shipped.
export function trigger(userCode: string): unknown {
  return eval(userCode);              // banned: dynamic code execution
}

export function trigger2(fn: string): unknown {
  return new Function(fn)();          // banned: dynamic code execution
}
