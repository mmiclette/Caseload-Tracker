/// <reference types="vite/client" />

interface ImportMetaEnv {
  /**
   * '1' only in the hosted-prototype build (set in the Dockerfile's frontend
   * stage). Turns on the sign-in page's one-click role picker and replaces
   * the PHI notice with a demonstration-data one. Undefined everywhere else.
   */
  readonly VITE_DEMO_MODE?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
