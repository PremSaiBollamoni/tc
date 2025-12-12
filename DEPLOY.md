# Deployment Guide

## ⚠️ IMPORTANT: Netlify Won't Work
Netlify only hosts static websites (HTML/CSS/JS). Your app is a Flask Python backend that needs a server.

## ✅ Recommended: Deploy on Vercel (FREE)

1. **Sign up**: Go to [vercel.com](https://vercel.com) and sign up with GitHub
2. **Connect GitHub**: Link your GitHub account
3. **Push code**: Push this project to a GitHub repository
4. **Import**: Click "New Project" → Import from GitHub
5. **Configure**: 
   - Framework: Other
   - Build Command: (leave empty)
   - Output Directory: (leave empty)
6. **Environment Variables**: In Vercel dashboard, go to Settings → Environment Variables and add:
   - Name: `DEEPINFRA_TOKEN`
   - Value: `sGnexJYRzOzcMH3x2Rzg9CusBH11poeO`
   - Environment: Production, Preview, Development (select all)
7. **Deploy**: Click Deploy!
8. **If it crashes**: Go to Functions tab in Vercel dashboard to see error logs

## ✅ FIXED: Serverless File System Issues

The app now uses `/tmp/` directory for all file operations, which is writable in serverless environments.

**Fixed Issues:**
- ✅ PDF page extraction now saves to `/tmp/temp_page_X.png`
- ✅ XML files saved to `/tmp/complete_XXX.xml`
- ✅ JSON files saved to `/tmp/XXX_complete.json`
- ✅ All temporary files use serverless-compatible paths

## Alternative: Railway (Also FREE)

1. Go to [railway.app](https://railway.app)
2. Sign up with GitHub
3. Click "Deploy from GitHub repo"
4. Select your repository
5. Add environment variable: `DEEPINFRA_TOKEN`
6. Deploy!

## Files Ready for Deployment:
- ✅ `vercel.json` - Vercel configuration
- ✅ `railway.json` - Railway configuration  
- ✅ `Procfile` - Process file
- ✅ `requirements.txt` - Python dependencies
- ✅ `runtime.txt` - Python version
- ✅ `wsgi.py` - WSGI entry point

## Your Live URL:
After deployment, you'll get a URL like:
- Vercel: `https://your-app-name.vercel.app`
- Railway: `https://your-app-name.up.railway.app`

Send this URL to your TL! 🚀