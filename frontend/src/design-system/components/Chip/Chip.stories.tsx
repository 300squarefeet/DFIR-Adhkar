import type { Meta, StoryObj } from "@storybook/react";

import { Chip } from "./Chip";

const meta: Meta<typeof Chip> = {
  title: "Design System/Chip",
  component: Chip,
  args: { children: "label" },
};
export default meta;
type Story = StoryObj<typeof Chip>;

export const Neutral: Story = { args: { variant: "neutral" } };
export const Info: Story = { args: { variant: "info" } };
export const Success: Story = { args: { variant: "success" } };
export const Warning: Story = { args: { variant: "warning" } };
export const Danger: Story = { args: { variant: "danger" } };
export const WithIcon: Story = { args: { variant: "success", leadingIcon: "check" } };
