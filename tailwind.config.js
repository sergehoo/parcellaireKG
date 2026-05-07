/** @type {import('tailwindcss').Config} */
module.exports = {
  // Tous les fichiers HTML / Python où on peut écrire des classes Tailwind
  // (templates Django, formulaires, widgets…). Le scan permet à Tailwind
  // de ne garder que les classes effectivement utilisées (purge / JIT).
  content: [
    "./templates/**/*.html",
    "./parcelaire/**/*.{py,html}",
    "./ai_construction/**/*.{py,html}",
  ],

  // Mode "safelist" : certaines classes sont injectées dynamiquement par le
  // backend (statusBadge, couleurs Tailwind selon le statut commercial).
  // On les whitelist pour que la passe de purge ne les retire pas.
  safelist: [
    {
      // toutes les variantes bg-*-100/text-*-700 utilisées dans les badges
      pattern:
        /(bg|text|ring|border)-(slate|sky|amber|emerald|violet|rose|indigo|orange|red|green|blue|yellow)-(50|100|200|300|400|500|600|700|800|900)/,
    },
  ],

  theme: {
    extend: {
      fontFamily: {
        sans: [
          "Inter",
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "Segoe UI",
          "Roboto",
          "sans-serif",
        ],
      },
      colors: {
        // Palette KAYDAN (orange chaleureux). Anciennement définie en
        // ligne via `tailwind.config = {...}` côté CDN. Conservée sous
        // les deux noms `kaydan-*` et `premium-*` pour ne rien casser
        // dans les templates existants.
        kaydan: {
          50: "#fff7ed",
          100: "#ffedd5",
          200: "#fed7aa",
          300: "#fdba74",
          400: "#fb923c",
          500: "#f97316",
          600: "#ea580c",
          700: "#c2410c",
          800: "#9a3412",
          900: "#7c2d12",
        },
        premium: {
          50: "#fff7ed",
          100: "#ffedd5",
          200: "#fed7aa",
          300: "#fdba74",
          400: "#fb923c",
          500: "#f97316",
          600: "#ea580c",
          700: "#c2410c",
          800: "#9a3412",
          900: "#7c2d12",
        },
        // Palette de la carte commerciale (vert émeraude). Remplace
        // l'ancien override `tailwind.config = {...}` du template
        // mapcommercial.html.
        commercial: {
          50: "#ecfdf5",
          100: "#d1fae5",
          200: "#a7f3d0",
          300: "#6ee7b7",
          400: "#34d399",
          500: "#10b981",
          600: "#059669",
          700: "#047857",
          800: "#065f46",
          900: "#064e3b",
        },
      },
      borderRadius: {
        "4xl": "2rem",
      },
      boxShadow: {
        soft: "0 20px 60px rgba(15, 23, 42, 0.12)",
        glass: "0 18px 42px rgba(15, 23, 42, 0.18)",
        premium: "0 24px 80px rgba(194, 65, 12, 0.18)",
        commercial: "0 24px 80px rgba(5, 150, 105, 0.18)",
      },
      transitionTimingFunction: {
        smooth: "cubic-bezier(0.22, 1, 0.36, 1)",
      },
    },
  },

  plugins: [],
};
