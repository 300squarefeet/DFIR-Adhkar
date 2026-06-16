import type { Meta, StoryObj } from "@storybook/react";

import { TLPBadge } from "./TLPBadge";

const meta: Meta<typeof TLPBadge> = {
  title: "Design System/TLPBadge",
  component: TLPBadge,
};
export default meta;
type Story = StoryObj<typeof TLPBadge>;

export const White: Story = { args: { tlp: "white" } };
export const Green: Story = { args: { tlp: "green" } };
export const Amber: Story = { args: { tlp: "amber" } };
export const AmberStrict: Story = { args: { tlp: "amber-strict" } };
export const Red: Story = { args: { tlp: "red" } };
