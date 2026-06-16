import type { TestRunnerConfig } from "@storybook/test-runner";

const config: TestRunnerConfig = {
  async preVisit(page) {
    await page.setViewportSize({ width: 1280, height: 800 });
  },
};

export default config;
