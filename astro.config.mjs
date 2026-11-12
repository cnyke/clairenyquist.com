import { defineConfig } from 'astro/config';
import tailwind from '@astrojs/tailwind';
import sitemap from '@astrojs/sitemap';

export default defineConfig({
  integrations: [
    tailwind(),
    sitemap({ filter: (page) => !page.includes('/animation') })
  ],
  redirects: {
    '/audubon': '/nonhuman-neighbors'
  },
  output: 'static',
  site: 'https://clairenyquist.com'
});

