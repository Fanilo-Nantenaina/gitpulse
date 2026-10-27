import { mount } from 'svelte';
import './app.css';
import App from './App.svelte';
import { app } from './lib/app.svelte';

document.documentElement.lang = app.lang;

export default mount(App, { target: document.getElementById('app')! });
