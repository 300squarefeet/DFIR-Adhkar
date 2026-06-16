import type { Meta, StoryObj } from "@storybook/react";
import { expect, fn, userEvent, within } from "@storybook/test";

import { Button } from "./Button";

const meta: Meta<typeof Button> = {
  title: "Design System/Button",
  component: Button,
  args: { children: "Save", onClick: fn() },
};
export default meta;

type Story = StoryObj<typeof Button>;

export const Filled: Story = {
  args: { variant: "filled" },
  play: async ({ canvasElement, args }) => {
    const c = within(canvasElement);
    await userEvent.click(c.getByRole("button"));
    await expect(args.onClick).toHaveBeenCalledOnce();
  },
};

export const Tonal: Story = { args: { variant: "tonal" } };
export const Outlined: Story = { args: { variant: "outlined" } };
export const Text: Story = { args: { variant: "text" } };
export const ErrorVariant: Story = { args: { variant: "error" } };

export const WithIcon: Story = { args: { variant: "filled", icon: "save" } };

export const SizeSm: Story = { args: { size: "sm", children: "sm" } };
export const SizeMd: Story = { args: { size: "md", children: "md" } };
export const SizeLg: Story = { args: { size: "lg", children: "lg" } };

export const Loading: Story = { args: { loading: true } };
export const Disabled: Story = { args: { disabled: true } };
