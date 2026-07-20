/** @type {import('tailwindcss').Config} */

export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    container: {
      center: true,
    },
    extend: {
      colors: {
        // Editorial Engineering Dashboard 色板
        ink: {
          900: "#0B1F3A", // 主墨蓝
          800: "#13294F",
          700: "#1E3A5F",
          600: "#2B4D75",
          500: "#3D6291",
          400: "#5B7BA8",
          300: "#8A9FC0",
          200: "#B8C7DC",
          100: "#DDE5F0",
          50: "#EEF2F8",
        },
        ember: {
          600: "#E5532A",
          500: "#FF6B35", // 强调橙
          400: "#FF8559",
          300: "#FFA88A",
          100: "#FFE5D9",
        },
        paper: {
          DEFAULT: "#F5F1E8", // 米白底
          warm: "#EFE8D6",
          card: "#FFFFFF",
        },
        stage: {
          s1: "#3B82F6", // 候选查找 - 蓝
          s2: "#8B5CF6", // 上游对照 - 紫
          s3: "#F59E0B", // 优化方案 - 琥珀
          s4: "#10B981", // 专利提取 - 绿
        },
      },
      fontFamily: {
        display: ['"Sora"', "system-ui", "sans-serif"],
        sans: ['"Inter"', "system-ui", "sans-serif"],
        mono: ['"JetBrains Mono"', "ui-monospace", "monospace"],
      },
      boxShadow: {
        card: "0 1px 3px rgba(11, 31, 58, 0.06), 0 1px 2px rgba(11, 31, 58, 0.04)",
        cardHover: "0 4px 12px rgba(11, 31, 58, 0.08), 0 2px 4px rgba(11, 31, 58, 0.06)",
        deep: "0 10px 30px rgba(11, 31, 58, 0.12)",
      },
    },
  },
  plugins: [],
};
