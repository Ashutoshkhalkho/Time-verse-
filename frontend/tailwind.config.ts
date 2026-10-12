import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: {
          DEFAULT: "#1261A0",
          hover: "#0E4E82",
          light: "#EAF3FB",
        },
        navy: {
          DEFAULT: "#17324D",
          dark: "#0F2133",
        },
        surface: {
          canvas: "#F7F9FC",
          card: "#FFFFFF",
          border: "#E2E7EE",
        },
        text: {
          main: "#1F2937",
          secondary: "#697586",
          muted: "#9AA5B5",
        },
        status: {
          success: "#16805D",
          warning: "#A96500",
          danger: "#B42332",
        },
      },
      borderRadius: {
        card: "14px",
        btn: "10px",
      },
    },
  },
  plugins: [],
};

export default config;
