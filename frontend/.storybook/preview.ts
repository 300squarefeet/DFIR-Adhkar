import type { Preview } from "@storybook/react";

import "../src/design-system/index.css";

const preview: Preview = {
  parameters: {
    backgrounds: { disable: true },
    controls: { matchers: { color: /(background|color)$/i } },
    layout: "centered",
  },
  globalTypes: {
    theme: {
      description: "Theme",
      defaultValue: "dark",
      toolbar: {
        title: "Theme",
        icon: "circlehollow",
        items: ["dark", "light"],
        dynamicTitle: true,
      },
    },
  },
  decorators: [
    (Story, ctx) => {
      document.documentElement.dataset.theme = (ctx.globals.theme as string) ?? "dark";
      return Story();
    },
  ],
};

export default preview;
