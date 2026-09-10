// SAST canary fixture — ts-no-document-write-innerhtml. Never shipped.
export function trigger(html: string): void {
  document.write(html);               // banned: raw HTML sink
}

export function trigger2(el: HTMLElement, html: string): void {
  el.innerHTML = html;                // banned: raw HTML sink
}
