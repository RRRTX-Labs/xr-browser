// SAST negative fixture — must NOT trigger any rule. The compliant WebUI
// shape: Lit templates, no eval, no raw HTML sinks, no client-side crypto.
import {LitElement, html} from "lit";

export class CleanView extends LitElement {
  render() {
    return html`<p>${this.text}</p>`;   // template literal, not innerHTML
  }
}
