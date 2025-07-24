import type { StorybookConfig } from "@storybook/nextjs";
import path from 'path';
import { fileURLToPath } from 'url';

// ESM module equivalent for __dirname
const currentDir = path.dirname(fileURLToPath(import.meta.url));

const config: StorybookConfig = {
  stories: [
    "../stories/**/*.mdx",
    "../stories/**/*.stories.@(js|jsx|mjs|ts|tsx)",
  ],
  addons: [
    "@storybook/addon-links",
    "@storybook/addon-essentials",
    "@storybook/addon-interactions",
    "@storybook/addon-themes",
    "storybook-dark-mode"
  ],
  framework: {
    name: "@storybook/nextjs",
    options: {},
  },
  docs: {
    autodocs: "tag",
  },
  staticDirs: ['../public'],
  webpackFinal: async (config) => {
    if (config.resolve) {
      config.resolve.alias = {
        ...config.resolve.alias,
        '@': path.resolve(currentDir, '../'),
        '@number-flow/react': path.resolve(currentDir, '../components/ui/number-flow-dev.tsx'),
      };
    }
    return config;
  },
};

export default config;
