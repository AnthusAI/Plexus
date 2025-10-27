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
    const webpack = require('webpack');
    
    if (config.resolve) {
      config.resolve.alias = {
        ...config.resolve.alias,
        '@': path.resolve(currentDir, '../'),
        '@number-flow/react': path.resolve(currentDir, '../components/ui/number-flow-dev.tsx'),
      };
    }
    
    // Use NormalModuleReplacementPlugin to replace AccountContext imports with mock
    config.plugins = config.plugins || [];
    config.plugins.push(
      new webpack.NormalModuleReplacementPlugin(
        /.*\/app\/contexts\/AccountContext/,
        path.resolve(currentDir, '../__mocks__/AccountContext.ts')
      )
    );
    
    return config;
  },
};

export default config;
