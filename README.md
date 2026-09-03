# Claire Nyquist

Personal portfolio website showcasing data visualization, public health analytics, and graphic design work. Built with Astro.build and Tailwind CSS, featuring interactive data visualizations exploring biology, epidemiology, and science communication.

**Live Site:** [clairenyquist.com](https://clairenyquist.com)

## Features

- **Interactive Data Visualizations** using D3.js and Leaflet
- **Respiratory Viruses Dashboard** - Minnesota public health surveillance data
- **Octopuses Biodiversity Map** - Global GBIF observations with interactive mapping
- **Mosquitoes Collection** - London Natural History Museum specimen database
- **Graphic Design Portfolio** - Science communication and visual design projects
- **Mobile-first responsive design** using Tailwind CSS
- **Automated deployment** via GitHub Actions
- **SEO optimized** with proper meta tags, structured data, and sitemaps
- **AI-search ready**: `public/llms.txt` and `public/llms-full.txt` describe the site in plain text for language models, `public/robots.txt` explicitly welcomes AI crawlers, and every page emits a Schema.org graph (Person, WebSite, WebPage) from `BaseLayout.astro`
- **Clean navigation** with dropdown menus and mobile support

## Pages

1. **Respiratory Viruses** - `/` - Interactive visualizations of RSV, influenza, COVID-19 data in Minnesota
2. **Octopuses** - `/octopuses` - Global octopus biodiversity data with interactive Leaflet map
3. **Mosquitoes** - `/mosquitoes` - 9,000+ mosquito specimens with filterable data visualizations
4. **Graphic Design** - `/graphic-design` - Portfolio of science communication and design projects
5. **Resumé** - `/resume` - Professional experience and skills
6. **About & Contact** - `/about-contact` - Background and contact information

## Getting Started

### Prerequisites

- Node.js 18+ 
- npm or yarn

### Installation

1. Install dependencies:
```bash
npm install
```

2. Start the development server:
```bash
npm run dev
```

3. Open your browser to `http://localhost:4321`

### Building for Production

```bash
npm run build
```

### Preview Production Build

```bash
npm run preview
```

## Technology Stack

- **Astro.build** - Static site generator with excellent performance
- **Tailwind CSS** - Utility-first CSS framework for styling
- **D3.js** - Data visualization library for interactive charts
- **Leaflet** - Interactive maps library for geographic visualizations
- **TypeScript** - Type safety and better developer experience
- **GitHub Actions** - Automated CI/CD deployment pipeline
- **Lexend** - Google Fonts typography for accessibility

## Deployment

This site is automatically deployed to [clairenyquist.com](https://clairenyquist.com) using GitHub Pages and GitHub Actions.

### Automated Deployment

Every push to the `main` branch triggers an automatic build and deployment:

1. GitHub Actions runs the workflow defined in `.github/workflows/deploy.yml`
2. Dependencies are installed and the site is built
3. The `dist` folder is deployed to GitHub Pages
4. Site is live at clairenyquist.com within minutes

### Manual Deployment

You can also trigger a deployment manually:

1. Go to the **Actions** tab in the GitHub repository
2. Select **"Deploy to GitHub Pages"** workflow
3. Click **"Run workflow"** → **"Run workflow"**

## Customization

### Updating Content

- **Layout & Branding**: Edit `src/layouts/BaseLayout.astro` for site-wide changes
- **Individual Pages**: Modify files in `src/pages/` directory
- **Data Files**: Update CSV files in `public/data/` directory
- **Images**: Replace files in `public/images/` directory

### Styling

- All styles use Tailwind CSS utility classes
- Custom color scheme can be modified in `tailwind.config.mjs`
- Font settings are configured in the base layout
- Google Analytics tracking ID in `src/layouts/BaseLayout.astro`

### Adding New Pages

1. Create a new `.astro` file in `src/pages/`
2. Use the `BaseLayout` component for consistent styling
3. Add navigation links in `src/layouts/BaseLayout.astro`
4. Rebuild and deploy

## Project Structure

```
clairenyquistwebsite/
├── .github/
│   └── workflows/
│       └── deploy.yml          # GitHub Actions deployment workflow
├── public/
│   ├── data/                   # Data files for visualizations
│   ├── images/                 # Static images and assets
│   ├── CNAME                   # Custom domain configuration
│   └── robots.txt              # SEO crawler instructions
├── src/
│   ├── layouts/
│   │   └── BaseLayout.astro    # Main layout component
│   ├── pages/                  # Page components (auto-routed)
│   │   ├── index.astro         # Homepage (Respiratory Viruses)
│   │   ├── octopuses.astro
│   │   ├── mosquitoes.astro
│   │   ├── graphic-design.astro
│   │   ├── resume.astro
│   │   └── about-contact.astro
│   └── env.d.ts
├── astro.config.mjs            # Astro configuration
├── tailwind.config.mjs         # Tailwind CSS configuration
├── tsconfig.json               # TypeScript configuration
└── package.json
```

## Mobile Responsiveness

The site is built mobile-first with responsive breakpoints:
- **sm**: 640px and up
- **md**: 768px and up  
- **lg**: 1024px and up
- **xl**: 1280px and up

All components are tested and optimized for mobile devices with touch-friendly interactions and adaptive layouts.

## License

© 2025 Claire Nyquist. All rights reserved.

