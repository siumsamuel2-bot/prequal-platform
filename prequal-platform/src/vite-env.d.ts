/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_URL: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

declare module './SubcontractorProfile.jsx' {
  import { ComponentType } from 'react';
  const component: ComponentType<unknown>;
  export default component;
}

declare module './CertificationAlerts.jsx' {
  import { ComponentType } from 'react';
  const component: ComponentType<unknown>;
  export default component;
}

declare module './CredentialUpload.jsx' {
  import { ComponentType } from 'react';
  const component: ComponentType<unknown>;
  export default component;
}