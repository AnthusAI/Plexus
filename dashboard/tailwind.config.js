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
        'bg-progress-background',
        'bg-progress-background-selected',
        'border-3',
        'border-secondary'
    ],
    theme: {
        extend: {
            borderRadius: {
                lg: 'var(--radius)',
                md: 'calc(var(--radius) - 2px)',
                sm: 'calc(var(--radius) - 4px)'
            },
            borderWidth: {
                '3': '0.75rem'
            },
            colors: {
                background: 'var(--background)',
                foreground: 'var(--foreground)',
                'foreground-selected': 'var(--foreground-selected)',
                'foreground-true': 'var(--foreground-true)',
                'foreground-false': 'var(--foreground-false)',
                focus: 'var(--focus)',
                attention: 'var(--attention)',
                card: {
                    DEFAULT: 'var(--card)',
                    foreground: 'var(--card-foreground)',
                    selected: 'var(--card-selected)',
                    'selected-foreground': 'var(--card-selected-foreground)'
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
                    foreground: 'var(--primary-foreground)',
                    selected: 'var(--primary-selected)',
                    'selected-foreground': 'var(--primary-selected-foreground)'
                },
                secondary: {
                    DEFAULT: 'var(--secondary)',
                    foreground: 'var(--secondary-foreground)',
                    selected: 'var(--secondary-selected)',
                    'selected-foreground': 'var(--secondary-selected-foreground)'
                },
                selected: {
                    DEFAULT: 'var(--selected)',
                    foreground: 'var(--selected-foreground)',
                    selected: 'var(--selected-selected)',
                    'selected-foreground': 'var(--selected-selected-foreground)'
                },
                muted: {
                    DEFAULT: 'var(--muted)',
                    foreground: 'var(--muted-foreground)'
                },
                accent: {
                    DEFAULT: 'var(--accent)',
                    foreground: 'var(--accent-foreground)',
                    selected: 'var(--accent-selected)',
                    'selected-foreground': 'var(--accent-selected-foreground)'
                },
                'navigation-icon': 'var(--navigation-icon)',
                destructive: {
                    DEFAULT: 'var(--destructive)',
                    foreground: 'var(--destructive-foreground)',
                    selected: 'var(--destructive-selected)',
                    'selected-foreground': 'var(--destructive-selected-foreground)'
                },
                border: 'var(--border)',
                frame: 'var(--frame)',
                input: 'var(--input)',
                ring: 'var(--ring)',
                'user-chat': 'var(--user-chat)',
                'plexus-chat': 'var(--plexus-chat)',
                'chart-1': {
                    DEFAULT: 'var(--chart-1)',
                    selected: 'var(--chart-1-selected)'
                },
                'chart-2': {
                    DEFAULT: 'var(--chart-2)',
                    selected: 'var(--chart-2-selected)'
                },
                'chart-3': {
                    DEFAULT: 'var(--chart-3)',
                    selected: 'var(--chart-3-selected)'
                },
                'chart-4': {
                    DEFAULT: 'var(--chart-4)',
                    selected: 'var(--chart-4-selected)'
                },
                'chart-5': {
                    DEFAULT: 'var(--chart-5)',
                    selected: 'var(--chart-5-selected)'
                },
                'chart-6': {
                    DEFAULT: 'var(--chart-6)',
                    selected: 'var(--chart-6-selected)'
                },
                'chart-7': {
                    DEFAULT: 'var(--chart-7)',
                    selected: 'var(--chart-7-selected)'
                },
                true: {
                    DEFAULT: 'var(--true)',
                    selected: 'var(--true-selected)'
                },
                false: {
                    DEFAULT: 'var(--false)',
                    selected: 'var(--false-selected)'
                },
                neutral: {
                    DEFAULT: 'var(--neutral)',
                    selected: 'var(--neutral-selected)'
                },
                'progress-background': 'var(--progress-background)',
                'progress-background-selected': 'var(--progress-background-selected)',
                'gauge-background': 'var(--gauge-background)',
                'gauge-inviable': 'var(--gauge-inviable)',
                'gauge-converging': 'var(--gauge-converging)', 
                'gauge-almost': 'var(--gauge-almost)',
                'gauge-viable': 'var(--gauge-viable)',
                'gauge-great': 'var(--gauge-great)',
                'editor-comment': 'var(--editor-comment)',
                'editor-key': 'var(--editor-key)',
                'editor-string': 'var(--editor-string)',
                'editor-number': 'var(--editor-number)',
                'editor-keyword': 'var(--editor-keyword)',
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
                },
                'gentle-bounce': {
                    '0%, 20%, 50%, 80%, 100%': {
                        transform: 'translateY(0)'
                    },
                    '10%': {
                        transform: 'translateY(-3px)'
                    },
                    '30%': {
                        transform: 'translateY(-2px)'
                    }
                },
                'attention-bounce': {
                    '0%, 15%, 35%, 55%, 100%': {
                        transform: 'translateY(0)'
                    },
                    '5%': {
                        transform: 'translateY(-8px)'
                    },
                    '25%': {
                        transform: 'translateY(-6px)'
                    },
                    '45%': {
                        transform: 'translateY(-4px)'
                    }
                }
            },
            animation: {
                'accordion-down': 'accordion-down 0.2s ease-out',
                'accordion-up': 'accordion-up 0.2s ease-out',
                'gentle-bounce': 'gentle-bounce 2.5s ease-in-out infinite',
                'attention-bounce': 'attention-bounce 2s ease-in-out infinite'
            }
        },
        screens: {
            'xs': '320px',
            'sm': '414px',
            'md': '640px',
            'lg': '768px',
            'xl': '1024px',
            '2xl': '1280px',
            '3xl': '1536px',
        }
    },
    plugins: [
        require("tailwindcss-animate"),
        require('@tailwindcss/container-queries')
    ],
}
