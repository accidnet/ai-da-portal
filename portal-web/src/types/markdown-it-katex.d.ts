declare module "markdown-it-katex" {
  import type MarkdownIt from "markdown-it";

  interface MarkdownItKatexOptions {
    throwOnError?: boolean;
    errorColor?: string;
    displayMode?: boolean;
    strict?: boolean | string | ((errorCode: string, errorMsg: string, token: string) => boolean | string);
    trust?: boolean | ((context: unknown) => boolean);
  }

  const markdownItKatex: MarkdownIt.PluginWithOptions<MarkdownItKatexOptions>;

  export default markdownItKatex;
}
