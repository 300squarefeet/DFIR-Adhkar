import type { Meta, StoryObj } from "@storybook/react";

import { SeverityBadge } from "./SeverityBadge";

const meta: Meta<typeof SeverityBadge> = {
  title: "Design System/SeverityBadge",
  component: SeverityBadge,
};
export default meta;
type Story = StoryObj<typeof SeverityBadge>;

export const Low: Story = { args: { level: 1 } };
export const Medium: Story = { args: { level: 2 } };
export const High: Story = { args: { level: 3 } };
export const Critical: Story = { args: { level: 4 } };

export const CompactLow: Story = { args: { level: 1, compact: true } };
export const CompactMedium: Story = { args: { level: 2, compact: true } };
export const CompactHigh: Story = { args: { level: 3, compact: true } };
export const CompactCritical: Story = { args: { level: 4, compact: true } };
