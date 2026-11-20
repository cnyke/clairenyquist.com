import { defineConfig } from 'astro/config';
import tailwind from '@astrojs/tailwind';
import sitemap from '@astrojs/sitemap';

export default defineConfig({
  integrations: [
    tailwind(),
    sitemap({ filter: (page) => !page.includes('/animation') })
  ],
  redirects: {
    '/audubon': '/nonhuman-neighbors',
    '/tcplot': 'https://tcplot.com',
    '/sci-art-club': 'https://sciart.club'
  },
  output: 'static',
  site: 'https://clairenyquist.com'
});

