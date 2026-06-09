#!/usr/bin/env node
const Tesseract = require('tesseract.js');
const path = require('path');
const fs = require('fs');

const args = process.argv.slice(2);
const imagePath = args.find(a => !a.startsWith('--'));
const langArg = args.find(a => a === '--lang');
const langIndex = langArg ? args.indexOf(langArg) : -1;
const languages = langIndex >= 0 && args[langIndex + 1] ? args[langIndex + 1] : 'chi_sim+eng';
const outputJson = args.includes('--json');

if (!imagePath) {
  console.error('Usage: node ocr.js <image> [--lang chi_sim+eng] [--json]');
  process.exit(1);
}

const resolvedPath = path.isAbsolute(imagePath) ? imagePath : path.join(process.cwd(), imagePath);
if (!fs.existsSync(resolvedPath)) {
  console.error('Error: Image not found:', resolvedPath);
  process.exit(1);
}

async function recognize() {
  try {
    const result = await Tesseract.recognize(resolvedPath, languages, { logger: m => {} });
    if (outputJson) {
      console.log(JSON.stringify({
        text: result.data.text,
        confidence: result.data.confidence,
        words: result.data.words.map(w => ({ text: w.text, confidence: w.confidence }))
      }, null, 2));
    } else {
      console.log(result.data.text);
    }
  } catch (error) {
    console.error('Error:', error.message);
    process.exit(1);
  }
}

recognize();
