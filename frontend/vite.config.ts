import path from 'path';
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
import devProxy from './proxyOptions.ts';

// https://vitejs.dev/config/
export default defineConfig(({ command, mode }) => ({
	plugins: [react(), tailwindcss()],
	server: {
		port: 8080,
		host: '0.0.0.0',
		// Only the dev server needs the bench proxy; builds and tests must not read site config.
		proxy: command === 'serve' && mode !== 'test' ? devProxy() : undefined,
	},
	resolve: {
		alias: {
			'@': path.resolve(__dirname, 'src'),
		},
	},
	build: {
		outDir: '../deployops/public/frontend',
		emptyOutDir: true,
		target: 'es2020',
	},
}));
