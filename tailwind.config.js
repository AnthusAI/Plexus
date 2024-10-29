module.exports = {
    darkMode: ["class"],
    content: [
        "./pages/**/*.{ts,tsx}",
        "./components/**/*.{ts,tsx}",
        "./app/**/*.{ts,tsx}",
        "./src/**/*.{ts,tsx}",
    ],
    safelist: [
        { pattern: /^bg-/ },
        { pattern: /^text-.*-foreground$/ },
        'grid',
    ],
    theme: {
        extend: {
            borderRadius: {
                lg: 'var(--radius)',
                md: 'calc(var(--radius) - 2px)',
                sm: 'calc(var(--radius) - 4px)'
            },
            colors: {
                background: 'var(--background)',
                foreground: 'var(--foreground)',
                card: {
                    DEFAULT: 'var(--card)',
                    foreground: 'var(--card-foreground)'
                },
                'card-light': {
                    DEFAULT: 'var(--card-light)',
                    foreground: 'var(--card-light-foreground)'
                },
                popover: {
                    DEFAULT: 'var(--popover)',
                    foreground: 'var(--popover-foreground)'
                },
                primary: {
                    DEFAULT: 'var(--primary)',
                    foreground: 'var(--primary-foreground)'
                },
                secondary: {
                    DEFAULT: 'var(--secondary)',
                    foreground: 'var(--secondary-foreground)'
                },
                muted: {
                    DEFAULT: 'var(--muted)',
                    foreground: 'var(--muted-foreground)'
                },
                accent: {
                    DEFAULT: 'var(--accent)',
                    foreground: 'var(--accent-foreground)'
                },
                destructive: {
                    DEFAULT: 'var(--destructive)',
                    foreground: 'var(--destructive-foreground)'
                },
                border: 'var(--border)',
                input: 'var(--input)',
                ring: 'var(--ring)',
                'user-chat': 'var(--user-chat)',
                'plexus-chat': 'var(--plexus-chat)',
                'chart-1': 'var(--chart-1)',
                'chart-2': 'var(--chart-2)',
                'chart-3': 'var(--chart-3)',
                'chart-4': 'var(--chart-4)',
                'chart-5': 'var(--chart-5)',
                'chart-6': 'var(--chart-6)',
                'chart-7': 'var(--chart-7)',
                true: 'var(--true)',
                false: 'var(--false)',
                neutral: 'var(--neutral)',
                'gauge-background': 'var(--gauge-background)',
                'gauge-inviable': 'var(--gauge-inviable)',
                'gauge-converging': 'var(--gauge-converging)', 
                'gauge-almost': 'var(--gauge-almost)',
                'gauge-viable': 'var(--gauge-viable)',
                'gauge-great': 'var(--gauge-great)',
            },
            keyframes: {
                'accordion-down': {
                    from: {
                        height: '0'
                    },
                    to: {
                        height: 'var(--radix-accordion-content-height)'
                    }
                },
                'accordion-up': {
                    from: {
                        height: 'var(--radix-accordion-content-height)'
                    },
                    to: {
                        height: '0'
                    }
                }
            },
            animation: {
                'accordion-down': 'accordion-down 0.2s ease-out',
                'accordion-up': 'accordion-up 0.2s ease-out'
            }
        },
        screens: {
            'xs': '414px',
            'sm': '640px',
            'md': '768px',
            'lg': '1024px',
            'xl': '1280px',
            '2xl': '1536px',
        }
    },
    plugins: [
        require("tailwindcss-animate"),
        require('@tailwindcss/container-queries')
    ],
}
