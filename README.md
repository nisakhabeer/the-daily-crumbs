# The Daily Crumbs — static site

Plain HTML/CSS, no build step. Deploy by connecting this repository to Vercel
(framework preset: Other, output directory: repository root).

## Contents
- `index.html` — homepage
- `posts/` — all articles + paginated listing (`posts/`, `posts/2/`, `posts/3/`)
- `category/<slug>/` — category listings with pagination
- `about/`, `contact/`

## Images
Photos are hotlinked from the live WordPress uploads
(`thedailycrumbs.wordpress.com/wp-content/uploads/...`) and are NOT copied here.
Photo credit/caption lines were stripped from article content per the owner's rule.

## After the Vercel domain is known
Re-run the generator (`tools/build.py`, reading the WordPress API dumps) with NEW_SITE_URL set to the Vercel domain so that
Pinterest Save buttons and sharing links point at the new site instead of the
WordPress URLs they currently carry.
