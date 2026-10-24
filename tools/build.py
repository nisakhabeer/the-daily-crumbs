#!/usr/bin/env python3
"""Build the static Daily Crumbs site from WordPress.com API data.

Reads /tmp/dc_posts.json and /tmp/dc_pages.json (public WP.com REST API).
Images are HOTLINKED from thedailycrumbs.wordpress.com uploads (not re-hosted).
Save-on-Pinterest and sharing URLs still point at the live WordPress URLs;
after the Vercel domain is known, set NEW_SITE_URL below and re-run to swap them.
"""
import json, re, html as htmllib, os, math
from datetime import datetime

NEW_SITE_URL = ""  # e.g. "https://the-daily-crumbs.vercel.app" once deployed
WP_BASE = "https://thedailycrumbs.wordpress.com"
OUT = "/home/hatch/workspace/daily-crumbs-site"
PER_PAGE = 10

posts_data = json.load(open("/tmp/dc_posts.json"))
pages_data = json.load(open("/tmp/dc_pages.json"))
posts = posts_data["posts"]  # newest first from API
pages = {p["slug"]: p for p in pages_data["posts"]}

# ---------- helpers ----------

def fmt_date(iso):
    try:
        return datetime.fromisoformat(iso).strftime("%b %d, %Y")
    except Exception:
        return iso[:10]

def plain_text(html_text):
    t = re.sub(r"<[^>]+>", " ", html_text or "")
    t = htmllib.unescape(t)
    return re.sub(r"\s+", " ", t).strip()

def clean_content(content):
    """Strip WP chrome + all 'Photo by' credit lines, keep article text exact."""
    c = content or ""
    c = re.sub(r"<!--.*?-->", "", c, flags=re.DOTALL)
    # Remove visible caption elements entirely
    c = re.sub(r"<figcaption\b[^>]*>.*?</figcaption>", "", c, flags=re.DOTALL | re.IGNORECASE)
    # Remove div wrappers but keep their contents
    c = re.sub(r"</?div\b[^>]*>", "", c, flags=re.IGNORECASE)
    # Rebuild img tags: keep src/alt/width/height only (drops data-image-caption etc.)
    def fix_img(m):
        tag = m.group(0)
        src = re.search(r'src="([^"]+)"', tag)
        alt = re.search(r'alt="([^"]*)"', tag)
        w = re.search(r'width="([^"]+)"', tag)
        h = re.search(r'height="([^"]+)"', tag)
        out = '<img src="%s"' % (src.group(1) if src else "")
        if alt:
            out += ' alt="%s"' % alt.group(1)
        if w:
            out += ' width="%s"' % w.group(1)
        if h:
            out += ' height="%s"' % h.group(1)
        out += ' loading="lazy">'
        return out
    c = re.sub(r"<img\b[^>]*>", fix_img, c, flags=re.IGNORECASE)
    # Strip class/style attributes from remaining tags
    c = re.sub(r'\sclass="[^"]*"', "", c)
    c = re.sub(r"\sstyle=\"[^\"]*\"", "", c)
    # Mark the Save button + pin image link for CSS
    c = re.sub(r'(<a\b[^>]*href="[^"]*pinterest\.com/pin/create[^"]*"[^>]*)(>Save on Pinterest</a>)',
                r'\1 class="save-btn"\2', c)
    c = re.sub(r'(<a\b[^>]*href="[^"]*pinterest\.com/pin/create[^"]*"[^>]*)(><img[^>]*-pin\.jpg[^>]*></a>)',
                r'\1 class="pin-link"\2', c)
    return c

def article_url(post):
    """URL used in share/save links: WP URL until NEW_SITE_URL is set."""
    if NEW_SITE_URL:
        return NEW_SITE_URL.rstrip("/") + "/posts/%s/" % post["slug"]
    return post["URL"]

def share_row(post):
    u = htmllib.escape(article_url(post), quote=True)
    t = htmllib.escape(post["title"], quote=True)
    return ('<div class="share-row"><span>Share this:</span> '
            '<a href="https://twitter.com/intent/tweet?url=%s&text=%s">X</a> '
            '<a href="https://www.facebook.com/sharer/sharer.php?u=%s">Facebook</a> '
            '<a href="https://www.pinterest.com/pin/create/button/?url=%s&description=%s">Pinterest</a> '
            '<a href="https://wa.me/?text=%s%%20%s">WhatsApp</a></div>' % (u, t, u, u, t, t, u))

# ---------- shared chrome ----------

NAV = [("Home", "/"), ("Recipes", "/category/all-recipes/"), ("Seasonal", "/category/seasonal/"),
       ("Dinner", "/category/dinner/"), ("Appetizers", "/category/appetizers/"),
       ("Desserts", "/category/desserts/"), ("About", "/about/")]

def chrome(title, body, desc=""):
    nav = "".join('<a href="%s">%s</a>' % (href, label) for label, href in NAV)
    foot = "".join('<a href="%s">%s</a>' % (href, label) for label, href in NAV)
    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>%s</title>
<meta name="description" content="%s">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700;800&family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/assets/style.css">
</head>
<body>
<div class="announce">Fresh &amp; Easy Recipes, Made with Love</div>
<header class="site-header">
<div class="logo"><a href="/">The Daily Crumbs</a></div>
<nav class="main-nav">%s</nav>
</header>
<main>
%s
</main>
<footer class="site-footer">
<nav class="footer-nav">%s</nav>
<p>&copy; 2026 The Daily Crumbs. All rights reserved.</p>
</footer>
</body>
</html>
""" % (htmllib.escape(title), htmllib.escape(desc)[:160], nav, body, foot)

def card(post):
    cats = sorted(post.get("categories", {}).values(), key=lambda c: c["name"])
    labels = ", ".join(c["name"] for c in cats).upper()
    feat = post.get("featured_image") or ""
    ex = plain_text(post.get("excerpt", ""))
    return """<article class="card">
<a href="/posts/%s/"><img src="%s" alt="%s" loading="lazy"></a>
<p class="card-cats">%s</p>
<h3 class="card-title"><a href="/posts/%s/">%s</a></h3>
<p class="card-date">%s</p>
<p class="card-excerpt">%s</p>
</article>""" % (post["slug"], feat, htmllib.escape(post["title"], quote=True), htmllib.escape(labels),
                  post["slug"], htmllib.escape(post["title"]), fmt_date(post["date"]), htmllib.escape(ex))

def pagination_row(base, page, total_pages):
    """base: URL prefix ending with '/', page 1 lives at base, page N at base+N/."""
    if total_pages <= 1:
        return '<nav class="pagination"><span class="page-num current">1</span></nav>'
    nums = []
    for n in range(1, total_pages + 1):
        href = base if n == 1 else "%s%d/" % (base, n)
        if n == page:
            nums.append('<span class="page-num current">%d</span>' % n)
        else:
            nums.append('<a class="page-num" href="%s">%d</a>' % (href, n))
    nxt = ""
    if page < total_pages:
        nxt_href = base if page + 1 == 1 else "%s%d/" % (base, page + 1)
        nxt = '<a class="page-next" href="%s">Next &rarr;</a>' % nxt_href
    prev = ""
    if page > 1:
        prev_href = base if page - 1 == 1 else "%s%d/" % (base, page - 1)
        prev = '<a class="page-prev" href="%s">&larr; Previous</a>' % prev_href
    return '<nav class="pagination">%s %s %s</nav>' % (prev, " ".join(nums), nxt)

def grid_page(items, base, page, heading, sub=""):
    total = max(1, math.ceil(len(items) / PER_PAGE))
    chunk = items[(page - 1) * PER_PAGE: page * PER_PAGE]
    cards = "".join(card(p) for p in chunk)
    body = '<section class="listing"><div class="container"><h1 class="page-heading">%s</h1>' % htmllib.escape(heading)
    if sub:
        body += '<p class="page-sub">%s</p>' % htmllib.escape(sub)
    body += '<div class="grid">%s</div>%s</div></section>' % (cards, pagination_row(base, page, total))
    return body, total

def write(path, text):
    full = os.path.join(OUT, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as f:
        f.write(text)

# ---------- CSS ----------

CSS = """
* { box-sizing: border-box; }
body { margin: 0; background: #FFF8EF; color: #49352A; font-family: 'Inter', sans-serif; line-height: 1.6; }
a { color: #49352A; }
h1, h2, h3, .logo a { font-family: 'Playfair Display', serif; color: #49352A; }
.announce { background: #B97563; color: #fff; text-align: center; padding: 10px 16px; font-size: 14px; font-weight: 600; letter-spacing: .04em; }
.site-header { background: #fff; border-bottom: 3px solid #B97563; text-align: center; padding: 24px 16px 18px; }
.logo a { font-size: 38px; font-weight: 800; text-decoration: none; }
.main-nav { margin-top: 14px; display: flex; flex-wrap: wrap; justify-content: center; gap: 26px; }
.main-nav a { text-decoration: none; font-size: 15px; font-weight: 600; }
.main-nav a:hover { color: #B97563; }
.container { max-width: 1200px; margin: 0 auto; padding: 0 24px; }
.hero { height: 460px; background-size: cover; background-position: center; position: relative; display: flex; align-items: center; }
.hero::after { content: ""; position: absolute; inset: 0; background: rgba(0,0,0,.4); }
.hero-inner { position: relative; z-index: 1; max-width: 680px; padding-left: 72px; color: #fff; }
.hero-eyebrow { font-size: 13px; font-weight: 700; letter-spacing: .18em; text-transform: uppercase; margin: 0 0 12px; }
.hero h1 { color: #fff; font-size: 48px; line-height: 1.15; margin: 0 0 14px; }
.hero-sub { font-size: 18px; margin: 0 0 22px; }
.btn { display: inline-block; background: #B97563; color: #fff; font-weight: 700; text-decoration: none; padding: 13px 26px; border-radius: 4px; }
.btn:hover { opacity: .92; }
.featured { padding: 40px 0 10px; }
.featured-card { background: #fff; display: flex; gap: 28px; padding: 24px; border: 1px solid #eee3d6; border-radius: 6px; align-items: center; }
.featured-card img { width: 45%; aspect-ratio: 3/2; object-fit: cover; border-radius: 4px; }
.featured-card h2 { margin: 0 0 10px; font-size: 30px; }
.featured-card h2 a { text-decoration: none; }
.section { padding: 34px 0; }
.section h2 { font-size: 30px; margin: 0 0 22px; }
.grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 26px; }
.card { background: #fff; border: 1px solid #eee3d6; border-radius: 6px; overflow: hidden; padding-bottom: 18px; }
.card img { width: 100%; aspect-ratio: 3/2; object-fit: cover; display: block; }
.card-cats { color: #B97563; font-size: 13px; font-weight: 700; letter-spacing: .06em; text-transform: uppercase; margin: 16px 18px 6px; }
.card-title { margin: 0 18px 6px; font-size: 22px; line-height: 1.3; }
.card-title a { text-decoration: none; }
.card-date { margin: 0 18px 8px; font-size: 13px; opacity: .75; }
.card-excerpt { margin: 0 18px; font-size: 15px; }
.center { text-align: center; margin: 30px 0 10px; }
.cat-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 22px; }
.cat-card { text-align: center; }
.cat-card img { width: 100%; aspect-ratio: 3/2; object-fit: cover; border-radius: 6px; display: block; }
.cat-card p { font-weight: 700; margin: 10px 0 0; }
.cat-card a { text-decoration: none; }
.cta-band { background: #B97563; color: #fff; text-align: center; padding: 44px 20px; }
.cta-band h2 { color: #fff; margin: 0 0 8px; font-size: 30px; }
.cta-band p { margin: 0 0 20px; }
.btn-white { display: inline-block; background: #fff; color: #B97563; font-weight: 700; text-decoration: none; padding: 13px 26px; border-radius: 4px; }
.about-sec { padding: 40px 0; }
.about-card { background: #fff; border: 1px solid #eee3d6; border-radius: 6px; padding: 30px; max-width: 820px; margin: 0 auto; text-align: center; }
.pagination { display: flex; justify-content: center; align-items: center; gap: 10px; margin: 36px 0 10px; flex-wrap: wrap; }
.page-num { display: inline-block; min-width: 40px; text-align: center; padding: 8px 10px; border: 1px solid #B97563; border-radius: 4px; text-decoration: none; font-weight: 600; color: #49352A; background: #fff; }
.page-num.current { background: #B97563; color: #fff; }
.page-next, .page-prev { background: #B97563; color: #fff; font-weight: 700; text-decoration: none; padding: 9px 18px; border-radius: 4px; }
.page-heading { font-size: 36px; margin: 34px 0 6px; }
.page-sub { margin: 0 0 26px; font-size: 17px; }
.listing { padding-bottom: 30px; }
.article { max-width: 760px; margin: 0 auto; padding: 36px 24px 30px; }
.article h1 { font-size: 40px; line-height: 1.25; margin: 0 0 10px; }
.article-meta { font-size: 14px; margin: 0 0 24px; opacity: .8; }
.article-content img { width: 100%; height: auto; display: block; margin: 22px 0; }
.article-content figure { margin: 22px 0; }
.article-content h2 { font-size: 28px; margin-top: 34px; }
.article-content h3 { font-size: 20px; margin-top: 22px; }
.article-content .pin-link { display: block; text-align: center; }
.article-content .pin-link img { width: 620px; max-width: 100%; margin: 18px auto; }
.article-content a.save-btn { display: block; width: fit-content; margin: 10px auto 26px; background: #B97563; color: #fff; font-weight: 700; text-decoration: none; padding: 13px 26px; border-radius: 4px; }
.share-row { border-top: 1px solid #eee3d6; margin-top: 30px; padding-top: 18px; display: flex; gap: 14px; flex-wrap: wrap; align-items: center; }
.share-row span { font-weight: 700; }
.site-footer { border-top: 3px solid #B97563; background: #fff; text-align: center; padding: 26px 16px; margin-top: 20px; }
.footer-nav { display: flex; flex-wrap: wrap; justify-content: center; gap: 26px; margin-bottom: 12px; }
.footer-nav a { text-decoration: none; font-weight: 600; }
@media (max-width: 900px) {
  .grid { grid-template-columns: repeat(2, 1fr); }
  .cat-grid { grid-template-columns: repeat(2, 1fr); }
  .featured-card { flex-direction: column; }
  .featured-card img { width: 100%; }
  .hero-inner { padding-left: 24px; }
  .hero h1 { font-size: 34px; }
}
@media (max-width: 600px) {
  .grid, .cat-grid { grid-template-columns: 1fr; }
  .article h1 { font-size: 30px; }
}
"""
write("assets/style.css", CSS)

# ---------- homepage ----------
latest = posts[:9]
hero_img = "https://images.pexels.com/photos/39551170/pexels-photo-39551170.jpeg?auto=compress&cs=tinysrgb&w=1600"
featured = posts[0]
feat_save = re.search(r'href="(https://www\.pinterest\.com/pin/create/button/[^"]+)"', featured["content"])
feat_save_url = htmllib.unescape(feat_save.group(1)) if feat_save else "https://www.pinterest.com/"

def cat_rep(slug):
    for p in posts:
        if slug in [c["slug"] for c in p.get("categories", {}).values()]:
            return p
    return posts[0]

cat_cards = ""
for slug, label in [("seasonal", "Seasonal"), ("dinner", "Dinner"), ("appetizers", "Appetizers"), ("desserts", "Desserts")]:
    rep = cat_rep(slug)
    cat_cards += ('<div class="cat-card"><a href="/category/%s/"><img src="%s" alt="%s" loading="lazy"><p>%s</p></a></div>'
                  % (slug, rep.get("featured_image", ""), htmllib.escape(label), label))

home_body = """
<section class="hero" style="background-image:url('%s')">
<div class="hero-inner">
<p class="hero-eyebrow">WELCOME TO THE DAILY CRUMBS</p>
<h1>A Little Crumb of Happiness in Every Bite</h1>
<p class="hero-sub">Easy recipes, cozy flavors &amp; delicious inspiration for every day.</p>
<a class="btn" href="/category/all-recipes/">EXPLORE RECIPES &rarr;</a>
</div>
</section>
<section class="featured"><div class="container"><div class="featured-card">
<a href="/posts/%s/"><img src="%s" alt="%s"></a>
<div><p class="card-cats">FEATURED RECIPE</p>
<h2><a href="/posts/%s/">%s</a></h2>
<p>%s</p>
<p><a class="btn" href="/posts/%s/">Get the Recipes</a></p></div>
</div></div></section>
<section class="section"><div class="container"><h2>The Latest</h2>
<div class="grid">%s</div>
<div class="center"><a class="btn" href="/category/all-recipes/">View All Recipes &rarr;</a></div>
</div></section>
<section class="section"><div class="container"><h2>Browse by Category</h2>
<div class="cat-grid">%s</div>
</div></section>
<section class="cta-band"><h2>Save Your Favorite Recipes</h2>
<p>Find a recipe you love? Save it to your Pinterest board for later.</p>
<a class="btn-white" href="%s">Save on Pinterest</a></section>
<section class="about-sec"><div class="container"><div class="about-card">
<h2>About The Daily Crumbs</h2>
<p>%s</p>
<p><a class="btn" href="/about/">Read Our Story &rarr;</a></p>
</div></div></section>
""" % (hero_img, featured["slug"], featured.get("featured_image", ""), htmllib.escape(featured["title"], quote=True),
       featured["slug"], htmllib.escape(featured["title"]), htmllib.escape(plain_text(featured.get("excerpt", ""))),
       featured["slug"], "".join(card(p) for p in latest), cat_cards,
       htmllib.escape(feat_save_url, quote=True),
       htmllib.escape(plain_text(pages["about-2"].get("excerpt", "")) if "about-2" in pages else ""))
write("index.html", chrome("The Daily Crumbs – Fresh & Easy Recipes, Made with Love", home_body,
                           "The Daily Crumbs — fresh and easy recipes, made with love."))

# ---------- posts listing with pagination ----------
n_post_pages = max(1, math.ceil(len(posts) / PER_PAGE))
for pg in range(1, n_post_pages + 1):
    body, _ = grid_page(posts, "/posts/", pg, "All Recipes",
                        "Every recipe from The Daily Crumbs, newest first.")
    path = "posts/index.html" if pg == 1 else "posts/%d/index.html" % pg
    write(path, chrome("All Recipes – The Daily Crumbs", body))

# ---------- category listings ----------
cat_posts = {}
for p in posts:
    for c in p.get("categories", {}).values():
        cat_posts.setdefault(c["slug"], {"name": c["name"], "items": []})["items"].append(p)
for slug, data in cat_posts.items():
    items = data["items"]
    npages = max(1, math.ceil(len(items) / PER_PAGE))
    for pg in range(1, npages + 1):
        body, _ = grid_page(items, "/category/%s/" % slug, pg, data["name"],
                            "%d recipes in %s." % (len(items), data["name"]))
        path = "category/%s/index.html" % slug if pg == 1 else "category/%s/%d/index.html" % (slug, pg)
        write(path, chrome("%s – The Daily Crumbs" % data["name"], body))

# ---------- article pages ----------
issues = []
for p in posts:
    content = clean_content(p["content"])
    if "Photo by" in content:
        issues.append((p["slug"], "residual 'Photo by' text remains"))
    cats = sorted(p.get("categories", {}).values(), key=lambda c: c["name"])
    labels = ", ".join(c["name"] for c in cats).upper()
    tags = ", ".join(sorted(p.get("tags", {}).keys()))
    feat = p.get("featured_image") or ""
    body = """<article class="article">
<p class="card-cats">%s</p>
<h1>%s</h1>
<p class="article-meta">%s</p>
%s
%s
</article>""" % (htmllib.escape(labels), htmllib.escape(p["title"]), fmt_date(p["date"]),
                  ('<div class="article-content"><img src="%s" alt="%s" loading="lazy">%s</div>'
                   % (feat, htmllib.escape(p["title"], quote=True), content)) if feat else
                  '<div class="article-content">%s</div>' % content,
                  share_row(p))
    if tags:
        body = body.replace("</article>", '<p class="article-meta">Tags: %s</p></article>' % htmllib.escape(tags))
    write("posts/%s/index.html" % p["slug"],
          chrome(p["title"] + " – The Daily Crumbs", body, plain_text(p.get("excerpt", ""))))

# ---------- about + contact ----------
for slug, out_path, heading in [("about-2", "about/index.html", "About The Daily Crumbs"),
                                ("contact", "contact/index.html", "Contact")]:
    if slug in pages:
        pg = pages[slug]
        body = '<article class="article"><h1>%s</h1><div class="article-content">%s</div></article>' % (
            heading, clean_content(pg["content"]))
        write(out_path, chrome(heading + " – The Daily Crumbs", body, plain_text(pg.get("excerpt", ""))))

# ---------- README ----------
write("README.md", """# The Daily Crumbs — static site

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
Re-run the generator with NEW_SITE_URL set to the Vercel domain so that
Pinterest Save buttons and sharing links point at the new site instead of the
WordPress URLs they currently carry.
""")

print("posts:", len(posts))
print("post listing pages:", n_post_pages)
print("categories:", {k: len(v["items"]) for k, v in cat_posts.items()})
print("issues:", issues)
total = 0
for root, _, files in os.walk(OUT):
    total += len(files)
print("total files:", total)
