import { defineConfig } from 'astro/config';
import tailwind from '@astrojs/tailwind';
import sitemap from '@astrojs/sitemap';

export default defineConfig({
  integrations: [
    tailwind(),
    sitemap()
  ],
  redirects: {
    '/audubon': '/nonhuman-neighbors'
  },
  output: 'static',
  site: 'https://clairenyquist.com'
});

