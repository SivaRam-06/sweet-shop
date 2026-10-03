from __future__ import annotations

from datetime import datetime, timedelta
from functools import wraps
import csv
import io
import os

from flask import Flask, Response, abort, current_app, flash, jsonify, redirect, render_template_string, request, session, url_for
from flask_login import LoginManager, UserMixin, current_user, login_required, login_user, logout_user
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash


app = Flask(__name__, static_folder="app/static", template_folder="app/templates")
app.config["SECRET_KEY"] = "sweet-shop-demo-secret"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///single_sweet_shop.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["ADMIN_EMAILS"] = {
    address.strip().lower()
    for address in os.environ.get("SWEET_SHOP_ADMIN_EMAILS", "").split(",")
    if address.strip()
}


db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"


class User(db.Model, UserMixin):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    cart_items = db.relationship("CartItem", back_populates="user", cascade="all, delete-orphan")
    orders = db.relationship("Order", back_populates="user", cascade="all, delete-orphan")
    profile = db.relationship("CustomerProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    preferences = db.relationship("CustomerSettings", back_populates="user", uselist=False, cascade="all, delete-orphan")
    onboarding = db.relationship("OnboardingProgress", back_populates="user", uselist=False, cascade="all, delete-orphan")
    access = db.relationship("UserAccess", back_populates="user", uselist=False, cascade="all, delete-orphan")
    reviews = db.relationship("ProductReview", back_populates="user", cascade="all, delete-orphan")
    wishlist_items = db.relationship("WishlistItem", back_populates="user", cascade="all, delete-orphan")

    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


class CustomerProfile(db.Model):
    __tablename__ = "customer_profiles"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), unique=True, nullable=False)
    bio = db.Column(db.String(240), nullable=False, default="")
    location = db.Column(db.String(120), nullable=False, default="")
    favorite_category = db.Column(db.String(60), nullable=False, default="Traditional Sweets")

    user = db.relationship("User", back_populates="profile")


class CustomerSettings(db.Model):
    __tablename__ = "customer_settings"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), unique=True, nullable=False)
    order_updates = db.Column(db.Boolean, nullable=False, default=True)
    newsletter = db.Column(db.Boolean, nullable=False, default=False)
    product_updates = db.Column(db.Boolean, nullable=False, default=True)

    user = db.relationship("User", back_populates="preferences")


class OnboardingProgress(db.Model):
    __tablename__ = "onboarding_progress"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), unique=True, nullable=False)
    step = db.Column(db.Integer, nullable=False, default=1)
    favorite_category = db.Column(db.String(60), nullable=False, default="Traditional Sweets")
    order_updates = db.Column(db.Boolean, nullable=False, default=True)
    newsletter = db.Column(db.Boolean, nullable=False, default=False)
    completed = db.Column(db.Boolean, nullable=False, default=False)

    user = db.relationship("User", back_populates="onboarding")


class Product(db.Model):
    __tablename__ = "products"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=False)
    price = db.Column(db.Float, nullable=False, default=0.0)
    stock = db.Column(db.Integer, nullable=False, default=0)
    image = db.Column(db.String(255), nullable=True)
    category = db.Column(db.String(60), nullable=False, default="General")

    cart_items = db.relationship("CartItem", back_populates="product", cascade="all, delete-orphan")
    order_items = db.relationship("OrderItem", back_populates="product", cascade="all, delete-orphan")
    reviews = db.relationship("ProductReview", back_populates="product", cascade="all, delete-orphan")
    wishlist_items = db.relationship("WishlistItem", back_populates="product", cascade="all, delete-orphan")


class CartItem(db.Model):
    __tablename__ = "cart_items"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)

    user = db.relationship("User", back_populates="cart_items")
    product = db.relationship("Product", back_populates="cart_items")


class Order(db.Model):
    __tablename__ = "orders"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    total = db.Column(db.Float, nullable=False, default=0.0)
    status = db.Column(db.String(30), default="pending")

    user = db.relationship("User", back_populates="orders")
    items = db.relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")


class OrderItem(db.Model):
    __tablename__ = "order_items"

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    price = db.Column(db.Float, nullable=False, default=0.0)

    order = db.relationship("Order", back_populates="items")
    product = db.relationship("Product", back_populates="order_items")


class ProductReview(db.Model):
    __tablename__ = "product_reviews"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    body = db.Column(db.String(1000), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", back_populates="reviews")
    product = db.relationship("Product", back_populates="reviews")


class WishlistItem(db.Model):
    __tablename__ = "wishlist_items"
    __table_args__ = (db.UniqueConstraint("user_id", "product_id", name="uq_wishlist_user_product"),)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", back_populates="wishlist_items")
    product = db.relationship("Product", back_populates="wishlist_items")


class OrderDetails(db.Model):
    __tablename__ = "order_details"

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), unique=True, nullable=False)
    recipient_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(30), nullable=False)
    address = db.Column(db.String(500), nullable=False)
    shipping_method = db.Column(db.String(30), nullable=False, default="standard")
    shipping_cost = db.Column(db.Float, nullable=False, default=0.0)
    subtotal = db.Column(db.Float, nullable=False, default=0.0)
    discount = db.Column(db.Float, nullable=False, default=0.0)
    payment_method = db.Column(db.String(30), nullable=False, default="cash")

    order = db.relationship("Order", backref=db.backref("details", uselist=False, cascade="all, delete-orphan"))


class UserAccess(db.Model):
    __tablename__ = "user_access"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), unique=True, nullable=False)
    role = db.Column(db.String(30), nullable=False, default="customer")
    status = db.Column(db.String(30), nullable=False, default="active")
    last_active = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", back_populates="access")


class AuditLog(db.Model):
    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    actor_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    actor_name = db.Column(db.String(80), nullable=False)
    action = db.Column(db.String(60), nullable=False)
    resource_type = db.Column(db.String(60), nullable=False)
    resource_id = db.Column(db.String(80), nullable=False, default="")
    details = db.Column(db.Text, nullable=False, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    actor = db.relationship("User")


class NewsletterSubscriber(db.Model):
    __tablename__ = "newsletter_subscribers"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


@app.context_processor
def inject_cart_preview():
    if not current_user.is_authenticated:
        return {"cart_count": 0, "mini_cart_items": []}
    items = get_cart_items_for_user(current_user.id)
    return {
        "cart_count": sum(item.quantity for item in items),
        "mini_cart_items": items[:3],
    }


BASE_HTML = """
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="description" content="Jai Hanuman Sweets — premium Indian sweets, snacks and festive treats delivered fresh.">
    <title>{{ title }} | Jai Hanuman Sweets</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@600;700&family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="{{ url_for('static', filename='css/style.css') }}">
    <style>
        :root {
          --bg: #fdf6e3;
          --panel: #fefdfb;
          --card: #fefdfb;
          --primary: #d64545;
          --primary-dark: #9e3535;
          --secondary: #4a7c8c;
          --accent: #e6c84b;
          --red: #d64545;
          --text: #3d3327;
          --muted: #746858;
          --line: #d4c4a8;
          --success: #5b8c5a;
          --shadow: 0 4px 8px rgba(60, 50, 40, 0.12);
          --paper-sheet: linear-gradient(135deg, rgba(255,255,255,.72), rgba(255,255,255,.28)), repeating-linear-gradient(0deg, rgba(125,99,64,.025) 0 1px, transparent 1px 4px), #fefdfb;
          --paper-kraft: #d4c4a8;
        }
    </style>
</head>
<body>
    <div class="global-progress" data-page-progress aria-hidden="true"><span></span></div>
    <div class="topbar">
        <div class="container topbar-inner">
            <span>Freshly prepared daily • Traditional recipes • Delivery across the city</span>
            <span>Call: +91 98765 43210</span>
        </div>
    </div>

    <nav class="navbar">
        <div class="container nav-inner">
            <a href="{{ url_for('home') }}" class="brand" aria-label="Jai Hanuman Sweets home">
                <span class="brand-mark">J</span>
                <span>Jai Hanuman<br><small>Sweets</small></span>
            </a>

            <div class="nav-links" id="storefront-navigation">
                <a href="{{ url_for('home') }}" {% if request.path == '/' %}aria-current="page"{% endif %}>Home</a>
                <a href="{{ url_for('products') }}" {% if request.path.startswith('/products') %}aria-current="page"{% endif %}>Shop</a>
                <details class="nav-mega"><summary>Categories</summary><div class="nav-mega-panel"><p class="eyebrow">Browse by craving</p><a href="{{ url_for('products', category='Traditional Sweets') }}">Traditional sweets</a><a href="{{ url_for('products', category='Milk Sweets') }}">Milk sweets</a><a href="{{ url_for('products', category='Gift Boxes') }}">Gift boxes</a><a href="{{ url_for('products', category='Snacks & Savouries') }}">Snacks &amp; savouries</a></div></details>
                <a href="{{ url_for('pricing') }}" {% if request.path == '/pricing' %}aria-current="page"{% endif %}>Gifting</a>
                <a href="{{ url_for('about') }}" {% if request.path == '/about' %}aria-current="page"{% endif %}>About</a>
                <a href="{{ url_for('faq') }}" {% if request.path == '/faq' %}aria-current="page"{% endif %}>FAQ</a>
                <div class="nav-mobile-account">{% if current_user.is_authenticated %}<a href="{{ url_for('dashboard') }}">My account</a><a href="{{ url_for('wishlist') }}">Saved sweets</a><a href="{{ url_for('logout') }}">Sign out</a>{% else %}<a href="{{ url_for('login') }}">Sign in</a><a href="{{ url_for('register') }}">Create an account</a>{% endif %}</div>
            </div>

            <div class="nav-actions">
                <button type="button" class="nav-search" data-command-open aria-haspopup="dialog" aria-expanded="false" aria-controls="global-search-palette" aria-label="Search products and pages" title="Search (Ctrl/⌘ K)">⌕</button>
                {% if current_user.is_authenticated %}<a href="{{ url_for('wishlist') }}" class="nav-wishlist" aria-label="Saved sweets">♡</a>{% endif %}
                <details class="mini-cart"><summary class="nav-cart" aria-label="Open mini cart">🛒{% if cart_count %}<span class="cart-count-badge">{{ cart_count }}</span>{% endif %}</summary><div class="mini-cart-popover"><strong>Your basket{% if cart_count %} · {{ cart_count }}{% endif %}</strong>{% for item in mini_cart_items %}<a href="{{ url_for('product_detail', product_id=item.product.id) }}"><span>{{ item.product.name }}</span><small>{{ item.quantity }} × ₹{{ '%.2f'|format(item.product.price) }}</small></a>{% endfor %}{% if not cart_count %}<p>Your basket is waiting for something sweet.</p>{% endif %}<a class="mini-cart-view" href="{{ url_for('cart') }}">View basket</a></div></details>
                {% if current_user.is_authenticated %}
                    <span class="welcome-text">Hi, {{ current_user.username }}</span>
                    <a href="{{ url_for('logout') }}" class="btn btn-secondary btn-small">Logout</a>
                {% else %}
                    <a href="{{ url_for('login') }}" class="btn btn-secondary btn-small">Login</a>
                    <a href="{{ url_for('register') }}" class="btn btn-primary btn-small">Sign Up</a>
                {% endif %}
            </div>
            <button type="button" class="storefront-menu-toggle" data-storefront-menu aria-expanded="false" aria-controls="storefront-navigation" aria-label="Open navigation"><span></span><span></span><span></span></button>
            <button type="button" class="storefront-menu-backdrop" data-storefront-menu-close aria-label="Close navigation"></button>
        </div>
    </nav>

    {% with messages = get_flashed_messages() %}
      {% if messages %}
        {% for msg in messages %}
          <div class="flash" role="status" data-toast><span>{{ msg }}</span><button type="button" data-toast-close aria-label="Dismiss message">×</button></div>
        {% endfor %}
      {% endif %}
    {% endwith %}

    <main class="page-shell" data-page-root data-transition-kind="{{ 'detail' if request.path.startswith('/products/') else 'main' }}">
        <div class="container">
            {{ content | safe }}
        </div>
    </main>

    <footer class="site-footer">
        <div class="container footer-grid">
            <div>
                <div class="brand footer-brand">
                    <span class="brand-mark">J</span>
                    <span>Jai Hanuman<br><small>Sweets</small></span>
                </div>
                <p>Premium Indian sweets and savouries prepared with traditional recipes, fresh ingredients, and a touch of festive joy.</p>
            </div>
            <div>
                <h4>Quick Links</h4>
                <ul>
                    <li><a href="{{ url_for('home') }}">Home</a></li>
                    <li><a href="{{ url_for('products') }}">Shop</a></li>
                    <li><a href="{{ url_for('products') }}">Offers</a></li>
                    <li><a href="{{ url_for('products') }}">Contact</a></li>
                </ul>
            </div>
            <div>
                <h4>Customer Care</h4>
                <ul>
                    <li>Order Support</li>
                    <li>Delivery Info</li>
                    <li>Bulk Orders</li>
                    <li>FAQs</li>
                </ul>
            </div>
            <div>
                <h4>Visit Us</h4>
                <ul>
                    <li>123 Main Market Road</li>
                    <li>Jaipur, Rajasthan</li>
                    <li>hello@jaihanumansweets.in</li>
                </ul>
            </div>
        </div>
        <div class="container footer-bottom">
            &copy; 2026 Jai Hanuman Sweets. All rights reserved.
        </div>
    </footer>
    <dialog class="command-palette storefront-command-palette" id="global-search-palette" data-global-command aria-label="Global search and commands">
        <form class="global-command-search" data-global-form><span aria-hidden="true">⌕</span><input type="search" placeholder="Search products, orders, or pages…" aria-label="Search products, orders, or pages" data-global-search autocomplete="off"><button type="button" data-clear-global-search aria-label="Clear search">×</button><kbd>ESC</kbd></form>
        <div class="global-command-recent" data-global-recent></div>
        <div class="global-command-results" data-global-results role="listbox" aria-label="Search results"></div>
        <p class="global-command-empty" data-global-empty hidden>No matches found. Try another search.</p>
        <footer><span>↑↓ to navigate</span><span>Enter to open</span><span>ESC to close</span></footer>
    </dialog>
    <script src="{{ url_for('static', filename='js/main.js') }}" defer></script>
</body>
</html>
"""

HOME_HTML = """
<section class="hero-section" data-stagger="grid" data-stagger-trigger="mount" data-stagger-direction="up">
    <div class="hero-copy">
        <p class="eyebrow">Traditional taste • freshly crafted</p>
        <h1>Sweet moments, made with the love of tradition.</h1>
        <p class="hero-text">From festive mithai to savory favourites, Jai Hanuman Sweets brings authentic Indian flavours to your home, celebrations, and everyday cravings.</p>
        <div class="hero-actions">
            <a href="{{ url_for('products') }}" class="btn btn-primary">Shop Sweets</a>
            <a href="{{ url_for('products') }}" class="btn btn-secondary">Explore Snacks</a>
        </div>
        <div class="hero-meta">
            <span>⭐ 4.9 customer rating</span>
            <span>🏠 Freshly packed daily</span>
        </div>
    </div>
    <div class="hero-visual">
        <div class="visual-badge">Festive favourites</div>
        <img src="https://images.unsplash.com/photo-1601050690597-df0568f70950?auto=format&fit=crop&w=900&q=80" alt="Fresh Indian sweets assortment" data-parallax="0.28">
    </div>
</section>

<section class="feature-grid" data-stagger="grid" data-stagger-direction="up">
    <div class="feature-card">
        <div class="feature-icon">🥭</div>
        <h3>Freshly Prepared</h3>
        <p>Made in small batches every day for rich taste and freshness.</p>
    </div>
    <div class="feature-card">
        <div class="feature-icon">🌾</div>
        <h3>Quality Ingredients</h3>
        <p>Only premium ingredients, clean preparation, and authentic recipes.</p>
    </div>
    <div class="feature-card">
        <div class="feature-icon">🎉</div>
        <h3>Festive Special</h3>
        <p>Perfect gifting, puja prasad, celebrations, and family moments.</p>
    </div>
    <div class="feature-card">
        <div class="feature-icon">🚚</div>
        <h3>Fast Delivery</h3>
        <p>Reliable ordering and fresh delivery right to your doorstep.</p>
    </div>
</section>

<section class="section-block">
    <div class="section-header">
        <div>
            <p class="eyebrow">Popular categories</p>
            <h2>Find your favourite taste</h2>
        </div>
    </div>
    <div class="category-grid" data-stagger="grid" data-stagger-direction="up">
        <a href="{{ url_for('products') }}" class="category-card">
            <img src="https://images.unsplash.com/photo-1551024601-bec78aea704b?auto=format&fit=crop&w=800&q=80" alt="Traditional sweets">
            <div class="category-body">
                <h3>Traditional Sweets</h3>
                <p>Classic mithai loved across generations.</p>
            </div>
        </a>
        <a href="{{ url_for('products') }}" class="category-card">
            <img src="https://images.unsplash.com/photo-1578985545062-69928b1d9587?auto=format&fit=crop&w=800&q=80" alt="Milk sweets">
            <div class="category-body">
                <h3>Milk Sweets</h3>
                <p>Rich and creamy favourites with a soft finish.</p>
            </div>
        </a>
        <a href="{{ url_for('products') }}" class="category-card">
            <img src="https://images.unsplash.com/photo-1519864600265-abb23847ef2c?auto=format&fit=crop&w=800&q=80" alt="Dry fruit sweets">
            <div class="category-body">
                <h3>Dry Fruit Sweets</h3>
                <p>Premium gifting options with a rich, indulgent taste.</p>
            </div>
        </a>
        <a href="{{ url_for('products') }}" class="category-card">
            <img src="https://images.unsplash.com/photo-1526318896980-cf78c088247c?auto=format&fit=crop&w=800&q=80" alt="Snacks and savouries">
            <div class="category-body">
                <h3>Snacks & Savouries</h3>
                <p>Crunchy and spice-kissed bites for every occasion.</p>
            </div>
        </a>
    </div>
</section>

<section class="section-block">
    <div class="section-header">
        <div>
            <p class="eyebrow">Best sellers</p>
            <h2>Fresh favourites for every craving</h2>
        </div>
        <a href="{{ url_for('products') }}" class="btn btn-secondary">View all</a>
    </div>

    <div class="product-grid" data-stagger="grid" data-stagger-direction="up">
        {% for product in products %}
        <article class="product-card">
            <div class="product-image-wrap">
                <img src="{{ product.image or 'https://images.unsplash.com/photo-1517433670267-08bbd4be890f?auto=format&fit=crop&w=800&q=80' }}" alt="{{ product.name }}">
                <span class="product-tag">Popular</span>
            </div>
            <div class="product-content">
                <div class="product-meta">
                    <span>{{ product.category }}</span>
                    {% if ratings.get(product.id) %}<a href="{{ url_for('product_detail', product_id=product.id) }}#reviews">★ {{ '%.1f'|format(ratings[product.id][0]) }} · {{ ratings[product.id][1] }}</a>{% else %}<span>Fresh batch</span>{% endif %}
                </div>
                <h3>{{ product.name }}</h3>
                <p>{{ product.description[:80] }}{% if product.description|length > 80 %}...{% endif %}</p>
                <div class="product-footer">
                    <strong>₹{{ '%.2f' % product.price }}</strong>
                    <form method="post" action="{{ url_for('add_to_cart', product_id=product.id) }}">
                        <button type="submit" class="btn btn-primary">Add to cart</button>
                    </form>
                </div>
            </div>
        </article>
        {% endfor %}
    </div>
</section>

<section class="feature-panel" data-stagger="grid" data-stagger-direction="right">
    <div class="panel-copy">
        <p class="eyebrow">Why families choose us</p>
        <h2>Authentic taste, trusted quality, and warm service.</h2>
        <ul>
            <li>Traditional recipes passed down with care</li>
            <li>Fresh ingredients and hygienic preparation</li>
            <li>Made for gifting, gatherings, and everyday indulgence</li>
        </ul>
    </div>
    <div class="mini-grid">
        <div class="mini-item"><span data-count-up>{{ total_orders }}</span> orders placed</div>
        <div class="mini-item"><span data-count-up>{{ product_count }}</span> sweets and treats</div>
        <div class="mini-item"><span>COD</span> payment on delivery</div>
    </div>
</section>

<section class="section-block home-bento-section">
    <div class="section-header"><div><p class="eyebrow">A little of everything</p><h2>Made for the moments worth sharing.</h2></div><a href="{{ url_for('pricing') }}" class="text-link">Explore gifting →</a></div>
    <div class="home-bento" data-stagger="grid" data-stagger-direction="up">
        <article class="bento-cell bento-featured"><div><p class="eyebrow">From our kitchen</p><h3>Traditional favourites, made fresh in small batches.</h3><a href="{{ url_for('products') }}" class="btn btn-primary">Browse the collection</a></div><img src="https://images.unsplash.com/photo-1601050690597-df0568f70950?auto=format&fit=crop&w=900&q=85" alt="A fresh assortment of Indian sweets" loading="lazy"></article>
        <article class="bento-cell bento-occasion"><span aria-hidden="true">✳</span><p class="eyebrow">A thoughtful gesture</p><h3>Bring a little sweetness along.</h3><a href="{{ url_for('pricing') }}">See gifting favourites →</a></article>
        <article class="bento-cell bento-quality"><span aria-hidden="true">♡</span><h3>Prepared with care.</h3><p>Careful ingredients and recipes made to be passed around.</p></article>
        <article class="bento-cell bento-delivery"><span class="bento-number">01</span><div><p class="eyebrow">From us to you</p><h3>Packed fresh for your table.</h3></div><a href="{{ url_for('faq') }}">Delivery questions →</a></article>
    </div>
</section>

<section class="section-block">
    <div class="section-header">
        <div>
            <p class="eyebrow">Customer love</p>
            <h2>What our customers say</h2>
        </div>
    </div>
    <div class="testimonial-carousel" data-testimonial-carousel aria-roledescription="carousel">
        <div class="testimonial-track" aria-live="polite">
            <article class="testimonial-card is-current" data-testimonial-slide><span class="quote-mark" aria-hidden="true">“</span><p>“The kaju katli was rich, fresh, and beautifully packed. It felt premium from the first bite.”</p><div class="testimonial-author"><span class="testimonial-avatar">P</span><strong>Priya S.</strong><span>Customer</span></div></article>
            <article class="testimonial-card" data-testimonial-slide hidden><span class="quote-mark" aria-hidden="true">“</span><p>“Very reliable service and the sweets tasted exactly like homemade mithai. Highly recommended.”</p><div class="testimonial-author"><span class="testimonial-avatar avatar-blue">R</span><strong>Rahul M.</strong><span>Customer</span></div></article>
            <article class="testimonial-card" data-testimonial-slide hidden><span class="quote-mark" aria-hidden="true">“</span><p>“We ordered for a family event and everyone loved the snacks and sweets. Great quality.”</p><div class="testimonial-author"><span class="testimonial-avatar avatar-green">N</span><strong>Nisha A.</strong><span>Customer</span></div></article>
        </div>
        <div class="testimonial-controls"><button type="button" data-testimonial-prev aria-label="Previous testimonial">←</button><div class="testimonial-dots" role="group" aria-label="Choose a testimonial"><button type="button" data-testimonial-dot="0" aria-label="Testimonial 1" aria-current="true"></button><button type="button" data-testimonial-dot="1" aria-label="Testimonial 2"></button><button type="button" data-testimonial-dot="2" aria-label="Testimonial 3"></button></div><button type="button" data-testimonial-next aria-label="Next testimonial">→</button></div>
    </div>
</section>

<section class="newsletter-box" id="newsletter" data-stagger="grid" data-stagger-direction="up">
    <div>
        <p class="eyebrow">Stay connected</p>
        <h2>Bring home festive joy every week.</h2>
    </div>
    <form method="post" action="{{ url_for('newsletter_signup') }}" class="newsletter-form" data-loading-form><label class="visually-hidden" for="newsletter-email">Email address</label><input id="newsletter-email" type="email" name="email" placeholder="Your email address" autocomplete="email" required><button type="submit" class="btn btn-secondary">Join the list</button></form>
</section>
"""

PRODUCTS_HTML = """
<section class="page-hero small-hero">
    <div>
        <p class="eyebrow">Our collection</p>
        <h1>Find your next favourite.</h1>
        <p>Small-batch sweets and savouries, prepared fresh for your table.</p>
    </div>
</section>

<div class="catalog-layout">
    <button class="filter-drawer-trigger" type="button" data-filter-open aria-controls="catalog-filters">Filters <span aria-hidden="true">⌄</span></button>
    <button class="filter-backdrop" type="button" data-filter-close aria-label="Close filters"></button>
    <aside class="filter-panel catalog-filters" id="catalog-filters">
        <div class="filter-heading"><h2>Refine your search</h2><button type="button" data-filter-close aria-label="Close filters">×</button></div>
        <form id="catalog-filters-form" method="get" action="{{ url_for('products') }}">
            <input type="hidden" name="q" value="{{ search }}">
            <input type="hidden" name="view" value="{{ view }}">
            <details class="filter-accordion" open><summary>Categories</summary><div class="filter-options">
                {% for category, count in categories %}<label><input type="checkbox" name="category" value="{{ category }}" {{ 'checked' if category in selected_categories else '' }}><span>{{ category }}</span><small>{{ count }}</small></label>{% endfor %}
            </div></details>
            <details class="filter-accordion" open><summary>Price range</summary><div class="price-slider" data-price-slider data-min="{{ absolute_min }}" data-max="{{ absolute_max }}"><div class="range-track"><span data-range-fill></span></div><input type="range" name="min_price" min="{{ absolute_min }}" max="{{ absolute_max }}" value="{{ min_price }}" aria-label="Minimum price" data-min-range><input type="range" name="max_price" min="{{ absolute_min }}" max="{{ absolute_max }}" value="{{ max_price }}" aria-label="Maximum price" data-max-range></div><div class="price-values"><label>From ₹<input type="number" min="{{ absolute_min }}" max="{{ absolute_max }}" name="min_display" value="{{ min_price }}" data-min-display></label><label>To ₹<input type="number" min="{{ absolute_min }}" max="{{ absolute_max }}" name="max_display" value="{{ max_price }}" data-max-display></label></div></details>
            <details class="filter-accordion" open><summary>Availability</summary><div class="filter-options"><label><input type="checkbox" name="in_stock" value="1" {{ 'checked' if in_stock else '' }}><span>Ready to ship</span><small>{{ available_count }}</small></label></div></details>
            <button class="btn btn-primary full-width apply-filters" type="submit">Apply filters</button>
            <a class="clear-filters" href="{{ url_for('products') }}">Clear all filters</a>
        </form>
    </aside>
    <section class="catalog-results">
        <div class="catalog-toolbar"><p class="results-count">Showing <strong>{{ first_result }}–{{ last_result }}</strong> of <strong>{{ total_results }}</strong> products{% if search %} for “{{ search }}”{% endif %}</p><div class="catalog-tools"><label class="sort-control">Sort by <select form="catalog-filters-form" name="sort" data-auto-submit><option value="relevance" {{ 'selected' if sort == 'relevance' else '' }}>Relevance</option><option value="price_asc" {{ 'selected' if sort == 'price_asc' else '' }}>Price: low to high</option><option value="price_desc" {{ 'selected' if sort == 'price_desc' else '' }}>Price: high to low</option><option value="newest" {{ 'selected' if sort == 'newest' else '' }}>Newest</option><option value="rating" {{ 'selected' if sort == 'rating' else '' }}>Top rated</option></select></label><div class="view-toggle" aria-label="Product view"><a class="{{ 'is-active' if view == 'grid' else '' }}" href="{{ url_for('products', view='grid', **view_args) }}" aria-label="Grid view">▦</a><a class="{{ 'is-active' if view == 'list' else '' }}" href="{{ url_for('products', view='list', **view_args) }}" aria-label="List view">☷</a></div></div></div>
        {% if products %}<div class="product-grid product-grid-large {{ 'is-list' if view == 'list' else '' }}" data-stagger="grid" data-stagger-direction="up">
        {% for product in products %}
        {% set rating = ratings.get(product.id) %}
        <article class="product-card listing-card">
            <div class="listing-image-area">
            <a class="product-image-wrap" href="{{ url_for('product_detail', product_id=product.id) }}">
                <img src="{{ product.image or 'https://images.unsplash.com/photo-1517433670267-08bbd4be890f?auto=format&fit=crop&w=800&q=80' }}" alt="{{ product.name }}" loading="lazy">
                {% if product.stock <= 5 %}<span class="product-tag sale-tag">Low stock</span>{% else %}<span class="product-tag">Fresh</span>{% endif %}
            </a>
            <div class="listing-quick-actions"><form method="post" action="{{ url_for('add_to_cart', product_id=product.id) }}"><input type="hidden" name="quantity" value="1"><input type="hidden" name="next" value="{{ request.full_path }}"><button class="btn btn-primary" type="submit">Add to basket</button></form><form method="post" action="{{ url_for('toggle_wishlist', product_id=product.id) }}"><input type="hidden" name="next" value="{{ request.full_path }}"><button class="wishlist-button {{ 'is-saved' if product.id in wishlist_ids else '' }}" type="submit" aria-label="{{ 'Remove from' if product.id in wishlist_ids else 'Add to' }} wishlist">{{ '♥' if product.id in wishlist_ids else '♡' }}</button></form></div>
            </div>
            <div class="product-content">
                <div class="product-meta">
                    <span>{{ product.category }}</span>
                    {% if rating %}<a href="{{ url_for('product_detail', product_id=product.id) }}#reviews">★ {{ '%.1f'|format(rating[0]) }} · {{ rating[1] }}</a>{% else %}<span>New batch</span>{% endif %}
                </div>
                <h3><a href="{{ url_for('product_detail', product_id=product.id) }}">{{ product.name }}</a></h3>
                <p>{{ product.description }}</p>
                <div class="product-footer">
                    <strong>₹{{ '%.2f' % product.price }}</strong>
                    <form method="post" action="{{ url_for('add_to_cart', product_id=product.id) }}">
                        <input type="hidden" name="quantity" value="1">
                        <button type="submit" class="btn btn-primary">Add to cart</button>
                    </form>
                </div>
            </div>
        </article>
        {% endfor %}
        </div>
        {% if page_count > 1 %}<nav class="catalog-pagination" aria-label="Product pages">{% if page > 1 %}<a href="{{ url_for('products', page=page-1, **filter_args) }}" aria-label="Previous page">←</a>{% endif %}{% for number in range(1, page_count + 1) %}<a class="{{ 'is-current' if number == page else '' }}" href="{{ url_for('products', page=number, **filter_args) }}" {% if number == page %}aria-current="page"{% endif %}>{{ number }}</a>{% endfor %}{% if page < page_count %}<a href="{{ url_for('products', page=page+1, **filter_args) }}" aria-label="Next page">→</a>{% endif %}</nav>{% endif %}
        {% else %}<div class="catalog-empty"><span aria-hidden="true">✳</span><h2>No sweets found for those filters.</h2><p>Try a wider price range or clear your filters to see the full collection.</p><a href="{{ url_for('products') }}" class="btn btn-secondary">Clear all filters</a></div>{% endif %}
    </section>
</div>
"""

PRODUCT_DETAIL_HTML = """
<section class="product-detail">
    <div class="detail-gallery">
        <button class="detail-image-box" type="button" data-open-lightbox aria-label="View {{ product.name }} image larger"><img src="{{ product.image or 'https://images.unsplash.com/photo-1517433670267-08bbd4be890f?auto=format&fit=crop&w=800&q=80' }}" alt="{{ product.name }}"></button>
        <div class="detail-thumbnails"><button class="is-active" type="button" data-gallery-image="{{ product.image or '' }}" aria-label="View product image"><img src="{{ product.image or '' }}" alt=""></button></div>
    </div>
    <div class="detail-copy">
        <p class="eyebrow">{{ product.category }}</p>
        <h1>{{ product.name }}</h1>
        <div class="detail-rating">{% if review_count %}{{ '★' * rating_average|round|int }}{{ '☆' * (5 - rating_average|round|int) }} <a href="#reviews">{{ '%.1f'|format(rating_average) }} · {{ review_count }} review{{ '' if review_count == 1 else 's' }}</a>{% else %}<span class="unrated">☆☆☆☆☆ · No reviews yet</span>{% endif %}</div>
        <div class="detail-price">₹{{ '%.2f' % product.price }}</div>
        <p class="detail-description">{{ product.description }}</p>
        <div class="detail-meta-box">
            {% if product.stock > 5 %}<span>In stock · {{ product.stock }} available</span>{% elif product.stock > 0 %}<span>Only {{ product.stock }} left</span>{% else %}<span>Currently unavailable</span>{% endif %}
            <span>Freshly made</span>
        </div>
        <div class="detail-actions">
            <form method="post" action="{{ url_for('add_to_cart', product_id=product.id) }}">
                <div class="quantity-control"><button type="button" data-quantity-change="-1" aria-label="Decrease quantity">−</button><input type="number" name="quantity" min="1" max="{{ product.stock or 1 }}" value="1" aria-label="Quantity"><button type="button" data-quantity-change="1" aria-label="Increase quantity">+</button></div>
                <button class="btn btn-primary" type="submit" {{ 'disabled' if product.stock <= 0 else '' }}>Add to basket</button>
                <button class="btn btn-secondary buy-now" type="submit" name="next" value="checkout" {{ 'disabled' if product.stock <= 0 else '' }}>Buy now</button>
            </form>
            <form method="post" action="{{ url_for('toggle_wishlist', product_id=product.id) }}"><button type="submit" class="wishlist-button detail-wishlist {{ 'is-saved' if is_wishlisted else '' }}" aria-label="{{ 'Remove from' if is_wishlisted else 'Add to' }} wishlist">{{ '♥' if is_wishlisted else '♡' }}</button></form>
        </div>
    </div>
</section>
<dialog class="product-lightbox" data-product-lightbox><button type="button" data-close-lightbox aria-label="Close image">×</button><img src="{{ product.image or '' }}" alt="{{ product.name }}"></dialog>
<section class="product-tabs" data-product-tabs><div role="tablist" aria-label="Product information"><button type="button" role="tab" aria-selected="true" data-product-tab="description">Description</button><button type="button" role="tab" aria-selected="false" data-product-tab="details">Details</button><button type="button" role="tab" aria-selected="false" data-product-tab="reviews">Reviews ({{ review_count }})</button></div><section role="tabpanel" data-product-panel="description"><p>{{ product.description }}</p><p>Prepared in small batches with carefully selected ingredients. Store in a cool, dry place and enjoy while fresh.</p></section><section role="tabpanel" data-product-panel="details" hidden><dl><dt>Category</dt><dd>{{ product.category }}</dd><dt>Availability</dt><dd>{{ 'In stock' if product.stock else 'Out of stock' }}</dd><dt>Product code</dt><dd>JHS-{{ '%04d'|format(product.id) }}</dd></dl></section><section role="tabpanel" id="reviews" data-product-panel="reviews" hidden>{% if reviews %}{% for review in reviews %}<article class="review-entry"><div class="review-stars">{{ '★' * review.rating }}{{ '☆' * (5 - review.rating) }}</div><strong>{{ review.user.username }}</strong><small>{{ review.created_at.strftime('%b %d, %Y') if review.created_at else '' }}</small><p>{{ review.body }}</p></article>{% endfor %}{% else %}<p>No reviews yet. Be the first to share what you think.</p>{% endif %}{% if current_user.is_authenticated %}<form method="post" action="{{ url_for('add_review', product_id=product.id) }}" class="review-form"><label>Your rating<select name="rating" required><option value="">Choose a rating</option>{% for score in range(5,0,-1) %}<option value="{{ score }}">{{ score }} star{{ '' if score == 1 else 's' }}</option>{% endfor %}</select></label><label>Your review<textarea name="body" maxlength="1000" required></textarea></label><button class="btn btn-primary" type="submit">Post review</button></form>{% else %}<a href="{{ url_for('login') }}">Sign in to leave a review</a>{% endif %}</section></div>
<section class="related-products"><div class="section-heading-inline"><div><p class="eyebrow">From the same shelf</p><h2>You may also like</h2></div><a href="{{ url_for('products') }}">Explore all →</a></div><div class="related-grid" data-stagger="grid" data-stagger-direction="up">{% for related in related_products %}<a class="related-product" href="{{ url_for('product_detail', product_id=related.id) }}"><img src="{{ related.image or '' }}" alt="" loading="lazy"><span>{{ related.category }}</span><strong>{{ related.name }}</strong><b>₹{{ '%.2f'|format(related.price) }}</b></a>{% endfor %}</div></section>
<div class="mobile-buy-bar"><span>₹{{ '%.2f'|format(product.price) }}</span><form method="post" action="{{ url_for('add_to_cart', product_id=product.id) }}"><input type="hidden" name="quantity" value="1"><button class="btn btn-primary" type="submit" {{ 'disabled' if product.stock <= 0 else '' }}>Add to basket</button></form></div>
"""

CART_HTML = """
<section class="page-hero small-hero">
    <div><p class="eyebrow">Your basket</p><h1>A few lovely things.</h1><p>{{ cart_items|length }} line item{{ '' if cart_items|length == 1 else 's' }} · {{ cart_count }} total piece{{ '' if cart_count == 1 else 's' }}</p></div>
</section>

{% if cart_items %}
<div class="cart-layout">
    <div class="cart-main"><section class="cart-items-list" aria-label="Basket items">{% for item in cart_items %}<article class="cart-item-card"><a class="cart-product-image" href="{{ url_for('product_detail', product_id=item.product.id) }}"><img src="{{ item.product.image or '' }}" alt="{{ item.product.name }}"></a><div class="cart-product-info"><a href="{{ url_for('product_detail', product_id=item.product.id) }}"><strong>{{ item.product.name }}</strong></a><small>{{ item.product.category }}</small><span>₹{{ '%.2f'|format(item.product.price) }} each</span></div><div class="cart-line-controls"><form method="post" action="{{ url_for('update_cart_item', item_id=item.id) }}" class="cart-quantity-control"><button name="quantity" value="{{ item.quantity - 1 }}" aria-label="Decrease {{ item.product.name }} quantity" {{ 'disabled' if item.quantity <= 1 else '' }}>−</button><span>{{ item.quantity }}</span><button name="quantity" value="{{ item.quantity + 1 }}" aria-label="Increase {{ item.product.name }} quantity" {{ 'disabled' if item.quantity >= item.product.stock else '' }}>+</button></form><strong>₹{{ '%.2f'|format(item.product.price * item.quantity) }}</strong><form method="post" action="{{ url_for('update_cart_item', item_id=item.id) }}"><button class="remove-item" name="action" value="remove">Remove</button></form></div></article>{% endfor %}</section>
    <section class="promo-section"><details {{ 'open' if promo_code else '' }}><summary>Have a sweet little discount?</summary><form method="post" action="{{ url_for('apply_promo') }}"><label for="promo-code">Promo code</label><div><input id="promo-code" name="code" value="{{ promo_code or '' }}" placeholder="Try SWEET10"><button class="btn btn-secondary" type="submit">Apply</button></div></form>{% if promo_code %}<form method="post" action="{{ url_for('remove_promo') }}"><span class="promo-applied">{{ promo_code }} applied · −₹{{ '%.2f'|format(discount) }}</span><button class="remove-item" type="submit">Remove code</button></form>{% endif %}</details></section>
    <section class="cart-cross-sells"><h2>Pair it with something lovely</h2><div>{% for product in suggestions %}<article><img src="{{ product.image or '' }}" alt=""><span><strong>{{ product.name }}</strong><small>₹{{ '%.2f'|format(product.price) }}</small></span><form method="post" action="{{ url_for('add_to_cart', product_id=product.id) }}"><button class="quick-add" type="submit" aria-label="Add {{ product.name }}">+</button></form></article>{% endfor %}</div></section></div>
    <aside class="summary-panel cart-summary"><h2>Order summary</h2><div class="summary-row"><span>Subtotal</span><strong>₹{{ '%.2f'|format(subtotal) }}</strong></div>{% if discount %}<div class="summary-row discount-row"><span>Discount · {{ promo_code }}</span><strong>−₹{{ '%.2f'|format(discount) }}</strong></div>{% endif %}<div class="summary-row"><span>Delivery</span><span>Calculated at checkout</span></div><div class="summary-row total"><span>Estimated total</span><strong>₹{{ '%.2f'|format(subtotal - discount) }}</strong></div><a href="{{ url_for('checkout') }}" class="btn btn-primary full-width">Continue to checkout <span aria-hidden="true">→</span></a><p class="checkout-reassurance">Secure checkout · Pay on delivery</p><a class="continue-shopping" href="{{ url_for('products') }}">← Continue shopping</a></aside>
</div>
{% else %}
<div class="empty-state cart-empty"><div class="empty-icon">♡</div><h2>Your basket is waiting.</h2><p>Fill it with a box of something lovely from our kitchen.</p><a href="{{ url_for('products') }}" class="btn btn-primary">Browse the sweets</a><section class="recently-viewed"><h3>Popular right now</h3><div>{% for product in suggestions %}<a href="{{ url_for('product_detail', product_id=product.id) }}">{{ product.name }} <span>₹{{ '%.2f'|format(product.price) }}</span></a>{% endfor %}</div></section></div>
{% endif %}
"""

CHECKOUT_HTML = """
<section class="page-hero small-hero">
    <div><p class="eyebrow">Secure checkout · Pay on delivery</p><h1>Make it yours.</h1><div class="checkout-progress"><span class="is-current">1 · Delivery</span><span>2 · Review</span><span>3 · Confirmed</span></div></div>
</section>

<div class="checkout-grid">
    <div class="panel-box">
        <form method="post" class="checkout-form" id="checkout-form" data-standard-shipping="{{ shipping_standard }}" data-express-shipping="{{ shipping_express }}" data-subtotal="{{ subtotal - discount }}" data-validate-form data-loading-form>
            <section class="checkout-section"><p class="eyebrow">01 · Delivery</p><h2>Where should we send it?</h2><div class="checkout-fields"><label>Full name<input type="text" name="name" autocomplete="name" value="{{ current_user.username }}" required></label><label>Email<input type="email" name="email" autocomplete="email" value="{{ current_user.email }}" required></label><label>Phone number<input type="tel" name="phone" autocomplete="tel" inputmode="tel" pattern="[0-9+() -]{8,20}" placeholder="For delivery updates" required></label><label class="wide-field">Delivery address<textarea name="address" autocomplete="street-address" rows="3" placeholder="House, street, area, city, PIN code" required>{{ address or '' }}</textarea></label></div><p class="checkout-reassurance">Your details are used to deliver and support this order.</p></section>
            <section class="checkout-section"><p class="eyebrow">02 · Shipping</p><h2>Choose your delivery</h2><div class="shipping-choices"><label><input type="radio" name="shipping" value="standard" checked><span><strong>Standard delivery</strong><small>Usually arrives in 3–5 days</small></span><b>{{ 'Free' if shipping_standard == 0 else '₹%.2f'|format(shipping_standard) }}</b></label><label><input type="radio" name="shipping" value="express"><span><strong>Express delivery</strong><small>Usually arrives in 1–2 days</small></span><b>₹{{ '%.2f'|format(shipping_express) }}</b></label></div></section>
            <section class="checkout-section"><p class="eyebrow">03 · Payment</p><h2>Payment method</h2><label class="payment-choice"><input type="radio" name="payment" value="cash" checked><span><strong>Cash on delivery</strong><small>Pay when your order arrives. Online card payments are not enabled yet.</small></span></label><p class="secure-note">♧ Your order and delivery details are sent securely.</p></section>
            <button type="submit" class="btn btn-primary full-width place-order-button">Place order · ₹<span data-checkout-total>{{ '%.2f'|format(subtotal - discount + shipping_standard) }}</span></button>
        </form>
    </div>

    <aside class="summary-panel checkout-summary"><div class="checkout-summary-heading"><h2>Your order</h2><a href="{{ url_for('cart') }}">Edit basket</a></div>{% for item in cart_items %}<div class="checkout-item"><span class="checkout-item-image"><img src="{{ item.product.image or '' }}" alt=""></span><span><strong>{{ item.product.name }}</strong><small>Qty {{ item.quantity }}</small></span><b>₹{{ '%.2f'|format(item.product.price * item.quantity) }}</b></div>{% endfor %}<div class="summary-row"><span>Subtotal</span><strong>₹{{ '%.2f'|format(subtotal) }}</strong></div>{% if discount %}<div class="summary-row discount-row"><span>Discount · {{ promo_code }}</span><strong>−₹{{ '%.2f'|format(discount) }}</strong></div>{% endif %}<div class="summary-row"><span>Standard delivery</span><strong>{{ 'Free' if shipping_standard == 0 else '₹%.2f'|format(shipping_standard) }}</strong></div><div class="summary-row total"><span>Total</span><strong>₹{{ '%.2f'|format(subtotal - discount + shipping_standard) }}</strong></div><p class="checkout-reassurance">No online payment is collected on this page.</p></aside>
</div>
"""

ORDER_CONFIRMATION_HTML = """
<section class="confirmation-header"><div class="success-mark" aria-hidden="true">✓</div><p class="eyebrow">Order placed</p><h1>Thank you, {{ order_details.recipient_name }}.</h1><p>Your sweets are being prepared with care.</p><div class="confirmation-number">Order <strong>#{{ order.id }}</strong><span>·</span>{{ order.created_at.strftime('%B %d, %Y') if order.created_at else '' }}</div></section>
<div class="confirmation-layout"><section class="paper-panel confirmation-items"><div class="section-heading-inline"><h2>Order summary</h2><button type="button" class="print-order" onclick="window.print()">Print receipt</button></div>{% for item in order.items %}<div class="checkout-item"><span class="checkout-item-image"><img src="{{ item.product.image or '' }}" alt=""></span><span><strong>{{ item.product.name }}</strong><small>Qty {{ item.quantity }}</small></span><b>₹{{ '%.2f'|format(item.price * item.quantity) }}</b></div>{% endfor %}<div class="summary-row"><span>Subtotal</span><strong>₹{{ '%.2f'|format(order_details.subtotal) }}</strong></div>{% if order_details.discount %}<div class="summary-row"><span>Discount</span><strong>−₹{{ '%.2f'|format(order_details.discount) }}</strong></div>{% endif %}<div class="summary-row"><span>Delivery</span><strong>{{ 'Free' if order_details.shipping_cost == 0 else '₹%.2f'|format(order_details.shipping_cost) }}</strong></div><div class="summary-row total"><span>Paid on delivery</span><strong>₹{{ '%.2f'|format(order.total) }}</strong></div></section><aside class="paper-panel delivery-card"><p class="eyebrow">On its way to</p><h2>{{ order_details.recipient_name }}</h2><p>{{ order_details.address }}</p><p>{{ order_details.phone }}<br>{{ order_details.email }}</p><div class="delivery-estimate"><span>Estimated arrival</span><strong>{{ estimated_delivery.strftime('%A, %B %d') }}</strong></div><div class="order-timeline"><span class="is-done">Order received</span><span>Being prepared</span><span>Out for delivery</span></div></aside></div>
<section class="confirmation-next"><p>We do not send automated confirmation emails yet. Your order details are saved in your account.</p><a href="{{ url_for('orders') }}" class="btn btn-secondary">Track order status</a><a href="{{ url_for('download_receipt', order_id=order.id) }}" class="btn btn-secondary">Download receipt</a><a href="{{ url_for('products') }}" class="btn btn-primary">Continue shopping</a><a href="mailto:hello@jaihanumansweets.in?subject=Order%20help%20%23{{ order.id }}" class="text-link">Need help with this order?</a></section>
"""

WISHLIST_HTML = """
<section class="page-hero small-hero"><div><p class="eyebrow">Saved for later</p><h1>Your favourites shelf.</h1><p>Keep the sweets you love close by.</p></div></section>
{% if products %}<div class="product-grid wishlist-grid" data-stagger="grid" data-stagger-direction="up">{% for product in products %}<article class="product-card"><a href="{{ url_for('product_detail', product_id=product.id) }}" class="product-image-wrap"><img src="{{ product.image or '' }}" alt="{{ product.name }}"><span class="product-tag">Saved</span></a><div class="product-content"><div class="product-meta"><span>{{ product.category }}</span><span>{{ 'In stock' if product.stock > 0 else 'Sold out' }}</span></div><h3><a href="{{ url_for('product_detail', product_id=product.id) }}">{{ product.name }}</a></h3><p>{{ product.description }}</p><div class="product-footer"><strong>₹{{ '%.2f'|format(product.price) }}</strong><div class="wishlist-actions"><form method="post" action="{{ url_for('add_to_cart', product_id=product.id) }}"><button class="btn btn-primary" type="submit" {{ 'disabled' if product.stock <= 0 else '' }}>Add to basket</button></form><form method="post" action="{{ url_for('toggle_wishlist', product_id=product.id) }}"><input type="hidden" name="next" value="/wishlist"><button class="remove-item" type="submit">Remove</button></form></div></div></div></article>{% endfor %}</div>{% else %}<div class="empty-state cart-empty"><div class="empty-icon">♡</div><h2>Your favourites will live here.</h2><p>Tap the heart on any sweet to save it for another day.</p><a href="{{ url_for('products') }}" class="btn btn-primary">Find a favourite</a></div>{% endif %}
"""

ADMIN_SHELL = """
<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>{{ page_title }} · Shop operations</title><link rel="stylesheet" href="{{ url_for('static', filename='css/style.css') }}"></head><body class="admin-page"><div class="admin-app"><aside class="admin-sidebar"><a class="brand" href="{{ url_for('admin_dashboard') }}"><span class="brand-mark">J</span><span>Jai Hanuman<br><small>Operations</small></span></a><p class="admin-nav-label">OPERATIONS</p><a class="{{ 'is-active' if active == 'dashboard' else '' }}" href="{{ url_for('admin_dashboard') }}">▦ <span>Overview</span></a><a class="{{ 'is-active' if active == 'users' else '' }}" href="{{ url_for('admin_users') }}">◉ <span>Customers</span></a><a class="{{ 'is-active' if active == 'analytics' else '' }}" href="{{ url_for('admin_analytics') }}">⌁ <span>Analytics</span></a><a class="{{ 'is-active' if active == 'audit' else '' }}" href="{{ url_for('admin_audit') }}">▤ <span>Activity log</span></a><a class="{{ 'is-active' if active == 'tools' else '' }}" href="{{ url_for('admin_tools') }}">⌘ <span>Internal tools</span></a><a href="{{ url_for('products') }}">↗ <span>Open storefront</span></a><div class="admin-sidebar-bottom"><span class="account-avatar small-avatar">{{ current_user.username[:1]|upper }}</span><span>{{ current_user.username }}<small>Shop administrator</small></span><a href="{{ url_for('logout') }}" aria-label="Sign out">↪</a></div></aside><main class="admin-main"><header class="admin-topbar"><div><span class="admin-crumb">Shop operations</span><span aria-hidden="true">/</span><strong>{{ page_title }}</strong></div><details><summary><span class="account-avatar small-avatar">{{ current_user.username[:1]|upper }}</span>{{ current_user.username }}⌄</summary><a href="{{ url_for('logout') }}">Sign out</a></details></header><section class="admin-content">{{ content|safe }}</section><footer class="admin-statusbar"><span><i class="status-dot"></i> Local database connected</span><span>Data updates on page refresh</span><span>Admin tools · Ctrl/⌘ K</span></footer></main><dialog class="command-palette" data-command-palette><form method="dialog"><input type="search" placeholder="Find a page or action…" aria-label="Search admin commands" data-command-search><button>Close</button></form><nav><a href="{{ url_for('admin_dashboard') }}">▦ Overview <kbd>G D</kbd></a><a href="{{ url_for('admin_users') }}">◉ Customers <kbd>G U</kbd></a><a href="{{ url_for('admin_analytics') }}">⌁ Analytics <kbd>G A</kbd></a><a href="{{ url_for('admin_audit') }}">▤ Activity log <kbd>G L</kbd></a><a href="{{ url_for('products') }}">↗ Storefront</a></nav></dialog></div><script src="{{ url_for('static', filename='js/main.js') }}" defer></script></body></html>
"""

ADMIN_DASHBOARD_HTML = """
<section class="admin-page-heading"><div><p class="eyebrow">{{ selected_period }} day view</p><h1>Good {{ current_user.username }}, here’s the shop today.</h1><p>Operational snapshot for Jai Hanuman Sweets.</p></div><form method="get"><label>Period <select name="days" onchange="this.form.submit()"><option value="7" {{ 'selected' if days == 7 else '' }}>Last 7 days</option><option value="30" {{ 'selected' if days == 30 else '' }}>Last 30 days</option><option value="90" {{ 'selected' if days == 90 else '' }}>Last 90 days</option></select></label><a href="{{ url_for('admin_analytics') }}" class="admin-action">New report</a></form></section>
<section class="admin-metric-grid"><a href="{{ url_for('admin_users') }}" class="admin-metric"><span>Customers</span><strong>{{ customer_count }}</strong><small>↑ {{ new_customers }} joined in period</small></a><a href="{{ url_for('admin_analytics') }}" class="admin-metric"><span>Revenue</span><strong>₹{{ '%.0f'|format(revenue) }}</strong><small>{{ order_count }} orders in period</small></a><a href="{{ url_for('admin_analytics') }}" class="admin-metric"><span>Average order</span><strong>₹{{ '%.0f'|format(average_order) }}</strong><small>Across completed orders</small></a><a href="{{ url_for('admin_analytics') }}" class="admin-metric {{ 'metric-alert' if low_stock else '' }}"><span>Low stock</span><strong>{{ low_stock }}</strong><small>Products with 5 or fewer left</small></a></section>
<div class="admin-dashboard-grid"><section class="admin-panel revenue-panel"><header><div><p class="eyebrow">Sales activity</p><h2>Revenue by day</h2></div><a href="{{ url_for('admin_analytics') }}">Full report →</a></header><div class="admin-bars" role="img" aria-label="Daily sales bar chart">{% for point in chart_data %}<div class="admin-bar-column"><span>₹{{ '%.0f'|format(point.amount) }}</span><i style="height: {{ point.height }}%"></i><small>{{ point.day }}</small></div>{% endfor %}</div></section><section class="admin-panel alerts-panel"><header><div><p class="eyebrow">Needs a look</p><h2>Shop alerts</h2></div></header>{% if low_stock_products %}{% for product in low_stock_products %}<a href="{{ url_for('admin_tools', q=product.name) }}" class="admin-alert-row"><span class="alert-indicator">!</span><span><strong>{{ product.name }}</strong><small>{{ product.stock }} remaining</small></span><span>→</span></a>{% endfor %}{% else %}<p class="admin-clean-state">All stocked products have more than five items available.</p>{% endif %}</section></div>
<section class="admin-panel admin-activity"><header><div><p class="eyebrow">Latest changes</p><h2>Recent activity</h2></div><a href="{{ url_for('admin_audit') }}">Audit log →</a></header>{% for entry in recent_activity %}<div class="admin-activity-row"><span class="activity-avatar">{{ entry.actor_name[:1]|upper }}</span><span><strong>{{ entry.actor_name }}</strong> {{ entry.action }} <b>{{ entry.resource_type }} {{ entry.resource_id }}</b><small>{{ entry.details }}</small></span><time>{{ entry.created_at.strftime('%b %d · %H:%M') if entry.created_at else '' }}</time></div>{% else %}<p class="admin-clean-state">Administrative actions will appear here.</p>{% endfor %}</section>
<section class="admin-quick-links"><a href="{{ url_for('admin_users') }}">＋ <span><strong>Manage customers</strong><small>Roles, status, and account details</small></span></a><a href="{{ url_for('admin_analytics') }}">↗ <span><strong>Export a report</strong><small>Order and product performance</small></span></a><a href="{{ url_for('admin_tools') }}">⌘ <span><strong>Open internal tools</strong><small>Compact order and product lookup</small></span></a></section>
"""

ADMIN_USERS_HTML = """
<section class="admin-page-heading"><div><p class="eyebrow">People and access</p><h1>Customer management</h1><p>{{ total_users }} accounts · Manage access and account status.</p></div><div><a class="admin-action" href="{{ url_for('admin_users_csv', **request.args) }}">Export CSV</a><button type="button" class="admin-action action-primary" data-open-add-user>＋ Add user</button></div></section>
<form class="admin-filter-bar" method="get"><label>Search<input name="q" value="{{ search }}" placeholder="Name or email"></label><label>Role<select name="role"><option value="">All roles</option>{% for value in ['customer','staff','admin'] %}<option value="{{ value }}" {{ 'selected' if role_filter == value else '' }}>{{ value|title }}</option>{% endfor %}</select></label><label>Status<select name="status"><option value="">All statuses</option>{% for value in ['active','suspended'] %}<option value="{{ value }}" {{ 'selected' if status_filter == value else '' }}>{{ value|title }}</option>{% endfor %}</select></label><label>Per page<select name="per_page"><option {{ 'selected' if per_page == 25 else '' }}>25</option><option {{ 'selected' if per_page == 50 else '' }}>50</option><option {{ 'selected' if per_page == 100 else '' }}>100</option></select></label><button class="admin-action action-primary">Filter</button><a class="admin-clear" href="{{ url_for('admin_users') }}">Clear</a></form>
<form id="bulk-user-action" method="post" action="{{ url_for('admin_bulk_users') }}" class="bulk-toolbar"><label><select name="action" required><option value="">Bulk action…</option><option value="activate">Activate</option><option value="suspend">Suspend</option><option value="delete">Delete selected</option></select></label><button class="admin-action" type="submit" data-bulk-submit>Apply to selected</button><span data-selected-count>0 selected</span></form>
<div class="admin-table-wrap"><table class="admin-table"><thead><tr><th><input type="checkbox" data-select-all aria-label="Select all users on this page"></th><th><a href="{{ url_for('admin_users', sort='name', dir='desc' if sort == 'name' and direction == 'asc' else 'asc', q=search, role=role_filter, status=status_filter) }}">Name ↕</a></th><th>Email</th><th>Role</th><th>Status</th><th>Last active</th><th>Actions</th></tr></thead><tbody>{% for user, access in users %}<tr><td><input type="checkbox" name="user_ids" value="{{ user.id }}" form="bulk-user-action" data-user-select aria-label="Select {{ user.username }}"></td><td><a class="table-user" href="{{ url_for('admin_user_detail', user_id=user.id) }}"><span class="account-avatar small-avatar">{{ user.username[:1]|upper }}</span><strong>{{ user.username }}</strong></a></td><td>{{ user.email }}</td><td><form method="post" action="{{ url_for('admin_user_access', user_id=user.id) }}" class="inline-access-form"><select name="role" aria-label="Role for {{ user.username }}"><option value="customer" {{ 'selected' if access.role == 'customer' else '' }}>Customer</option><option value="staff" {{ 'selected' if access.role == 'staff' else '' }}>Staff</option><option value="admin" {{ 'selected' if access.role == 'admin' else '' }} disabled>Admin</option></select><input type="hidden" name="status" value="{{ access.status }}"><button class="visually-hidden" type="submit">Save role</button></form></td><td><span class="user-status status-{{ access.status }}"><i></i>{{ access.status|title }}</span></td><td>{{ access.last_active.strftime('%b %d, %Y') if access.last_active else '—' }}</td><td><a class="row-action" href="{{ url_for('admin_user_detail', user_id=user.id) }}">View</a><form method="post" action="{{ url_for('admin_user_access', user_id=user.id) }}"><input type="hidden" name="role" value="{{ access.role }}"><input type="hidden" name="status" value="{{ 'suspended' if access.status == 'active' else 'active' }}"><button class="row-action" type="submit">{{ 'Suspend' if access.status == 'active' else 'Activate' }}</button></form></td></tr>{% else %}<tr><td colspan="7" class="admin-empty-row">No customers match these filters.</td></tr>{% endfor %}</tbody></table></div>
<nav class="admin-pagination" aria-label="User pages"><span>{{ first_user }}–{{ last_user }} of {{ total_users }}</span>{% if page > 1 %}<a href="{{ url_for('admin_users', page=page-1, q=search, role=role_filter, status=status_filter, per_page=per_page) }}">Previous</a>{% endif %}{% if page < pages %}<a href="{{ url_for('admin_users', page=page+1, q=search, role=role_filter, status=status_filter, per_page=per_page) }}">Next</a>{% endif %}</nav>
<dialog class="admin-dialog" data-add-user-dialog><form method="post" action="{{ url_for('admin_create_user') }}"><p class="eyebrow">New account</p><h2>Add a customer or staff member</h2><label>Name<input name="username" required></label><label>Email<input name="email" type="email" required></label><label>Temporary password<input name="password" minlength="12" required><small>Share it securely; users can reset it through customer care.</small></label><label>Role<select name="role"><option value="customer">Customer</option><option value="staff">Staff</option></select></label><div><button type="button" class="admin-action" data-close-add-user>Cancel</button><button class="admin-action action-primary">Create account</button></div></form></dialog>
<dialog class="admin-dialog" data-bulk-delete-dialog><form method="dialog"><h2>Delete selected accounts?</h2><p>This permanently removes the selected accounts and their associated order history.</p><div><button class="admin-action" value="cancel">Cancel</button><button class="admin-action action-danger" value="confirm" data-confirm-bulk-delete>Delete accounts</button></div></form></dialog>
"""

ADMIN_USER_DETAIL_HTML = """
<section class="admin-page-heading"><div><p class="eyebrow"><a href="{{ url_for('admin_users') }}">Customers</a> / Account {{ user.id }}</p><h1>{{ user.username }}</h1><p>{{ user.email }}</p></div><a href="{{ url_for('admin_users') }}" class="admin-action">← All customers</a></section><div class="admin-detail-grid"><section class="admin-panel"><h2>Account details</h2><dl class="admin-detail-list"><dt>Role</dt><dd>{{ access.role|title }}</dd><dt>Status</dt><dd>{{ access.status|title }}</dd><dt>Member since</dt><dd>{{ user.created_at.strftime('%B %d, %Y') if user.created_at else '—' }}</dd><dt>Last active</dt><dd>{{ access.last_active.strftime('%B %d, %Y %H:%M') if access.last_active else '—' }}</dd><dt>Profile location</dt><dd>{{ user.profile.location if user.profile else 'Not provided' }}</dd><dt>Orders</dt><dd>{{ orders|length }}</dd></dl></section><section class="admin-panel"><h2>Access controls</h2><form method="post" action="{{ url_for('admin_user_access', user_id=user.id) }}" class="admin-edit-form"><label>Role<select name="role"><option value="customer" {{ 'selected' if access.role == 'customer' else '' }}>Customer</option><option value="staff" {{ 'selected' if access.role == 'staff' else '' }}>Staff</option></select></label><label>Status<select name="status"><option value="active" {{ 'selected' if access.status == 'active' else '' }}>Active</option><option value="suspended" {{ 'selected' if access.status == 'suspended' else '' }}>Suspended</option></select></label><button class="admin-action action-primary">Save access</button></form></section><section class="admin-panel admin-detail-orders"><h2>Order history</h2>{% for order in orders %}<div class="admin-order-line"><a href="{{ url_for('admin_tools', order=order.id) }}">Order #{{ order.id }} · {{ order.created_at.strftime('%b %d, %Y') if order.created_at else '' }}</a><strong>₹{{ '%.2f'|format(order.total) }}</strong><span>{{ order.status|title }}</span></div>{% else %}<p>No orders on this account.</p>{% endfor %}</section><section class="admin-panel"><h2>Recent audit events</h2>{% for entry in events %}<p class="admin-detail-event"><strong>{{ entry.action }}</strong> {{ entry.resource_type }} {{ entry.resource_id }}<small>{{ entry.created_at.strftime('%b %d, %Y %H:%M') if entry.created_at else '' }}</small></p>{% else %}<p>No account events recorded.</p>{% endfor %}</section></div>
"""

ADMIN_AUDIT_HTML = """
<section class="admin-page-heading"><div><p class="eyebrow">Accountability</p><h1>Activity log</h1><p>Administrative actions retained for 365 days.</p></div><a href="{{ url_for('admin_audit_csv', **request.args) }}" class="admin-action">Export CSV</a></section><form method="get" class="admin-filter-bar audit-filter"><label>Search<input name="q" value="{{ search }}" placeholder="Actor, action, resource"></label><label>Action<select name="action"><option value="">All actions</option>{% for item in actions %}<option {{ 'selected' if action_filter == item else '' }}>{{ item }}</option>{% endfor %}</select></label><label>Resource<select name="resource"><option value="">All resources</option>{% for item in resources %}<option {{ 'selected' if resource_filter == item else '' }}>{{ item }}</option>{% endfor %}</select></label><button class="admin-action action-primary">Apply</button><a class="admin-clear" href="{{ url_for('admin_audit') }}">Clear</a></form><section class="admin-panel audit-panel"><div class="audit-retention">Showing {{ entries|length }} of {{ total }} events · Export logs for long-term storage.</div>{% for entry in entries %}<article class="audit-row"><span class="audit-dot audit-{{ entry.action|lower }}"></span><span class="audit-avatar">{{ entry.actor_name[:1]|upper }}</span><div><strong>{{ entry.actor_name }}</strong><p><b>{{ entry.action|title }}</b> {{ entry.resource_type }}{% if entry.resource_id %} <a href="{{ url_for('admin_users') if entry.resource_type == 'User' else url_for('admin_tools') }}">#{{ entry.resource_id }}</a>{% endif %}</p><small>{{ entry.details }}</small></div><time>{{ entry.created_at.strftime('%b %d, %Y · %H:%M') if entry.created_at else '' }}</time></article>{% else %}<p class="admin-clean-state">No audit events match those filters.</p>{% endfor %}</section>
"""

ADMIN_TOOLS_HTML = """
<section class="admin-page-heading"><div><p class="eyebrow">Compact workspace</p><h1>Internal tools</h1><p>Quick search across recent orders and current inventory.</p></div><div class="keyboard-hint">Press <kbd>Ctrl</kbd>/<kbd>⌘</kbd> + <kbd>K</kbd> for commands</div></section><form method="get" class="tools-search"><label>Search products, customers, or order IDs<input name="q" value="{{ search }}" autofocus placeholder="Start typing…"></label><button class="admin-action action-primary">Search</button><span class="save-status">{{ 'Searching: ' + search if search else 'Ready' }}</span></form><div class="tools-split"><section class="admin-panel tools-master"><header><h2>Matching orders</h2><span>{{ orders|length }} results</span></header>{% for order in orders %}<a class="tool-result {{ 'is-selected' if selected_order and selected_order.id == order.id else '' }}" href="{{ url_for('admin_tools', q=search, order=order.id) }}"><span class="tool-result-mark">#{{ order.id }}</span><span><strong>{{ order.user.username }}</strong><small>{{ order.created_at.strftime('%b %d · %H:%M') if order.created_at else '' }} · {{ order.status|title }}</small></span><b>₹{{ '%.2f'|format(order.total) }}</b></a>{% else %}<p class="admin-clean-state">No matching orders. Search a customer or order ID.</p>{% endfor %}<header class="tool-product-heading"><h2>Inventory matches</h2><span>{{ products|length }} results</span></header>{% for product in products %}<a class="tool-result" href="{{ url_for('product_detail', product_id=product.id) }}"><span class="tool-result-mark">{{ product.name[:1] }}</span><span><strong>{{ product.name }}</strong><small>{{ product.category }} · {{ product.stock }} in stock</small></span><b>₹{{ '%.2f'|format(product.price) }}</b></a>{% endfor %}</section><section class="admin-panel tools-detail"><h2>{% if selected_order %}Order #{{ selected_order.id }}{% else %}Order detail{% endif %}</h2>{% if selected_order %}<p>Customer: <a href="{{ url_for('admin_user_detail', user_id=selected_order.user_id) }}">{{ selected_order.user.username }}</a></p><p>Status: <strong>{{ selected_order.status|title }}</strong></p>{% if selected_order.details %}<p>Ship to: {{ selected_order.details.recipient_name }} · {{ selected_order.details.address }}</p>{% endif %}{% for item in selected_order.items %}<div class="admin-order-line"><span>{{ item.product.name }} × {{ item.quantity }}</span><strong>₹{{ '%.2f'|format(item.price * item.quantity) }}</strong></div>{% endfor %}<strong class="tools-total">Total ₹{{ '%.2f'|format(selected_order.total) }}</strong><form method="post" action="{{ url_for('admin_order_status', order_id=selected_order.id) }}" class="admin-edit-form"><label>Update status<select name="status">{% for status in ['pending','confirmed','preparing','shipped','delivered','cancelled'] %}<option value="{{ status }}" {{ 'selected' if selected_order.status == status else '' }}>{{ status|title }}</option>{% endfor %}</select></label><button class="admin-action action-primary">Update order</button></form>{% else %}<p class="admin-clean-state">Choose an order from the results list to inspect delivery and item details.</p>{% endif %}</section></div>
"""

ADMIN_ANALYTICS_HTML = """
<section class="admin-page-heading"><div><p class="eyebrow">Shop performance</p><h1>Analytics</h1><p>Compare order volume and sales by day.</p></div><form method="get"><label>Period <select name="days" onchange="this.form.submit()"><option value="7" {{ 'selected' if days == 7 else '' }}>7 days</option><option value="30" {{ 'selected' if days == 30 else '' }}>30 days</option><option value="90" {{ 'selected' if days == 90 else '' }}>90 days</option></select></label><label class="compare-toggle"><input type="checkbox" name="compare" value="1" {{ 'checked' if compare else '' }} onchange="this.form.submit()"> Compare previous</label><a href="{{ url_for('admin_analytics_csv', days=days) }}" class="admin-action">Export CSV</a></form></section><section class="admin-metric-grid analytics-metrics"><article class="admin-metric"><span>Revenue</span><strong>₹{{ '%.0f'|format(revenue) }}</strong><small>{{ '₹%.0f previous period'|format(previous_revenue) if compare else 'Selected period' }}</small></article><article class="admin-metric"><span>Orders</span><strong>{{ order_count }}</strong><small>{{ 'Previous: ' + previous_orders|string if compare else 'Placed in period' }}</small></article><article class="admin-metric"><span>Avg. basket</span><strong>₹{{ '%.0f'|format(average_order) }}</strong><small>Revenue / order count</small></article><article class="admin-metric"><span>New customers</span><strong>{{ new_customers }}</strong><small>Accounts created in period</small></article></section><section class="admin-panel analytics-chart"><header><div><p class="eyebrow">Daily totals</p><h2>Revenue and orders</h2></div></header><div class="admin-bars analytics-bars">{% for point in chart_data %}<div class="admin-bar-column"><span>₹{{ '%.0f'|format(point.amount) }}</span><i style="height:{{ point.height }}%"></i><small>{{ point.day }}</small></div>{% endfor %}</div></section><div class="analytics-bottom"><section class="admin-panel"><h2>Top products by units</h2>{% for product, quantity in top_products %}<div class="top-product-row"><span>{{ product.name }}</span><b>{{ quantity }}</b></div>{% else %}<p class="admin-clean-state">No sales in this period yet.</p>{% endfor %}</section><section class="admin-panel"><h2>Period comparison</h2><div class="comparison-line"><span>This period</span><strong>₹{{ '%.2f'|format(revenue) }}</strong></div><div class="comparison-line"><span>Previous period</span><strong>₹{{ '%.2f'|format(previous_revenue) }}</strong></div><p class="comparison-difference">{{ '%.1f'|format(change_percent) }}% {{ 'up' if change_percent >= 0 else 'down' }} from the previous period</p></section></div>
"""

PRICING_HTML = """
<section class="page-hero small-hero"><div><p class="eyebrow">Thoughtful gifting</p><h1>Find the right box for your table.</h1><p>Choose sweets by the piece and price shown. For celebration-size or custom assortments, contact the shop.</p></div></section><section class="pricing-product-grid">{% for product in products %}<article class="pricing-product"><span class="eyebrow">{{ product.category }}</span><h2>{{ product.name }}</h2><p>{{ product.description }}</p><div><strong>₹{{ '%.2f'|format(product.price) }}</strong><small>per listed item</small></div><a class="btn btn-primary" href="{{ url_for('product_detail', product_id=product.id) }}">View sweet</a></article>{% endfor %}</section><section class="bulk-gifting"><div><p class="eyebrow">For bigger gatherings</p><h2>Planning a celebration?</h2><p>Tell us the date, guest count, and flavours you love. We’ll help you plan an assortment.</p></div><a class="btn btn-secondary" href="mailto:hello@jaihanumansweets.in?subject=Bulk%20sweets%20enquiry">Ask about a bulk order</a></section><section class="faq-list"><h2>Good to know</h2><details><summary>How is each item priced?</summary><p>Prices are shown next to each product and reflect the listed product unit.</p></details><details><summary>Can I request a larger assortment?</summary><p>Yes. Contact customer care with your date and approximate quantity so the team can confirm availability.</p></details><details><summary>When is delivery free?</summary><p>Standard delivery is free for orders of ₹1,200 or more. Express delivery is priced at checkout.</p></details></section>
"""

AUTH_SHELL = """
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="theme-color" content="#fdf6e3">
    <title>{{ title }} | Jai Hanuman Sweets</title>
    <link rel="stylesheet" href="{{ url_for('static', filename='css/style.css') }}">
</head>
<body class="auth-page">
    {% with messages = get_flashed_messages() %}{% if messages %}<div class="auth-flash" role="alert">{% for message in messages %}<p>{{ message }}</p>{% endfor %}</div>{% endif %}{% endwith %}
    {{ content | safe }}
    <script src="{{ url_for('static', filename='js/main.js') }}" defer></script>
</body>
</html>
"""

AUTH_FORM_HTML = """
<div class="auth-layout">
    <aside class="auth-brand-panel">
        <a href="{{ url_for('home') }}" class="brand auth-brand" aria-label="Jai Hanuman Sweets home">
            <span class="brand-mark">J</span><span>Jai Hanuman<br><small>Sweets</small></span>
        </a>
        <div class="auth-brand-copy">
            <p class="eyebrow">A little joy, delivered</p>
            <h1>Made with care.<br>Shared with love.</h1>
            <p>Bring a box of fresh mithai to the moments that matter, from our family kitchen to yours.</p>
            <div class="auth-note"><span aria-hidden="true">✳</span><span>Small-batch sweets, packed fresh every day.</span></div>
        </div>
        <span class="auth-brand-footer">Traditional recipes · Since 1987</span>
    </aside>
    <main class="auth-main">
        <div class="auth-form-card">
            <a href="{{ url_for('home') }}" class="auth-mobile-brand">Jai Hanuman Sweets</a>
            <div class="auth-header">
                <p class="eyebrow">{{ 'Your account' if mode == 'login' else 'Join our table' }}</p>
                <h2>{{ 'Welcome back' if mode == 'login' else 'Create your account' }}</h2>
                <p>{{ 'Sign in to see your orders and saved favourites.' if mode == 'login' else 'A sweeter way to keep track of every order.' }}</p>
            </div>
            <form method="post" class="auth-form" data-auth-form data-validate-form>
                {% if mode == 'signup' %}
                <label>Full name<input type="text" name="username" autocomplete="name" required minlength="2" value="{{ request.form.get('username', '') }}"></label>
                <label>Email address<input type="email" name="email" autocomplete="email" required value="{{ request.form.get('email', '') }}"></label>
                {% else %}
                <label>Email or username<input type="text" name="username" autocomplete="username" required value="{{ request.form.get('username', '') }}"></label>
                {% endif %}
                <label class="password-label">Password
                    <span class="password-control"><input type="password" name="password" autocomplete="{{ 'new-password' if mode == 'signup' else 'current-password' }}" required {% if mode == 'signup' %}minlength="8"{% endif %} data-password-input><button type="button" class="password-toggle" data-password-toggle aria-label="Show password">Show</button></span>
                </label>
                {% if mode == 'login' %}<div class="auth-options"><label class="check-label"><input type="checkbox" name="remember"> Remember me</label><a href="{{ url_for('forgot_password') }}">Forgot password?</a></div>{% endif %}
                <button type="submit" class="btn btn-primary full-width auth-submit"><span data-loading-label="{{ 'Signing you in…' if mode == 'login' else 'Creating your account…' }}">{{ 'Sign in' if mode == 'login' else 'Create account' }}</span><span class="button-spinner" aria-hidden="true"></span></button>
            </form>
            <div class="auth-divider"><span>or continue with</span></div>
            <div class="social-login" aria-label="Social sign-in options">
                <button type="button" disabled title="Google sign-in is not configured"><span aria-hidden="true">G</span> Google</button>
                <button type="button" disabled title="GitHub sign-in is not configured"><span aria-hidden="true">⌘</span> GitHub</button>
                <button type="button" disabled title="Apple sign-in is not configured"><span aria-hidden="true">●</span> Apple</button>
            </div>
            <p class="auth-switch">{{ 'New to Jai Hanuman?' if mode == 'login' else 'Already have an account?' }} <a href="{{ url_for('register' if mode == 'login' else 'login') }}">{{ 'Create an account' if mode == 'login' else 'Sign in' }}</a></p>
            <p class="auth-legal"><a href="{{ url_for('terms') }}">Terms</a><a href="{{ url_for('terms') }}#privacy">Privacy</a><a href="mailto:hello@jaihanumansweets.in">Help</a></p>
        </div>
    </main>
</div>
"""

ABOUT_HTML = """
<section class="about-hero"><div><p class="eyebrow">Our kitchen, your table</p><h1>Good sweets bring people closer.</h1><p>We make familiar favourites with care, fresh ingredients, and the kind of attention usually reserved for family.</p><a href="{{ url_for('products') }}" class="btn btn-primary">Explore the collection</a></div><img src="https://images.unsplash.com/photo-1601050690597-df0568f70950?auto=format&fit=crop&w=1100&q=85" alt="A selection of traditional sweets ready to share"></section>
<section class="about-story"><div><p class="eyebrow">A little more about us</p><h2>Rooted in tradition. Made for today.</h2></div><p>Every batch begins with thoughtful ingredients and familiar methods. From a small box for afternoon tea to sweets for a family celebration, we want every order to feel considered, fresh, and ready to share.</p></section>
<section class="about-values" data-stagger="grid" data-stagger-direction="up"><article><span aria-hidden="true">✳</span><h3>Made fresh</h3><p>Small batches help us keep each order at its best.</p></article><article><span aria-hidden="true">♡</span><h3>Made with care</h3><p>Traditional flavours, prepared with attention to the details.</p></article><article><span aria-hidden="true">▧</span><h3>Made to share</h3><p>Thoughtful boxes for everyday treats and meaningful gatherings.</p></article></section>
<section class="about-cta"><p class="eyebrow">Come by the kitchen</p><h2>Find a new favourite to pass around.</h2><a href="{{ url_for('products') }}" class="btn btn-primary">Shop sweets</a></section>
"""

TERMS_HTML = """
<main class="policy-page"><a class="brand" href="{{ url_for('home') }}"><span class="brand-mark">J</span><span>Jai Hanuman<br><small>Sweets</small></span></a><section class="paper-panel"><p class="eyebrow">The fine print</p><h1>Terms &amp; privacy</h1><p>We use your account details to manage orders and provide customer support. We do not sell personal information.</p><h2 id="privacy">Privacy</h2><p>Order and contact details are retained only to support your purchases and account preferences.</p><a class="btn btn-primary" href="{{ url_for('home') }}">Back to the shop</a></section></main>
"""

ACCOUNT_SHELL = """
<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>{{ page_title }} | Jai Hanuman Sweets</title><link rel="stylesheet" href="{{ url_for('static', filename='css/style.css') }}"></head>
<body class="account-page"><div class="account-app" data-account-app>
    <aside class="dashboard-sidebar" id="account-sidebar" aria-label="Account navigation">
        <a href="{{ url_for('home') }}" class="brand account-brand"><span class="brand-mark">J</span><span class="sidebar-label">Jai Hanuman<br><small>Sweets</small></span></a>
        <button type="button" class="sidebar-collapse" data-sidebar-collapse aria-label="Collapse sidebar" title="Collapse sidebar"><span aria-hidden="true">⇤</span></button>
        <nav class="sidebar-nav">
            <p class="sidebar-group sidebar-label">Your account</p>
            <a class="nav-item {{ 'is-active' if active_page == 'dashboard' else '' }}" href="{{ url_for('dashboard') }}" {% if active_page == 'dashboard' %}aria-current="page"{% endif %}><span class="nav-icon" aria-hidden="true">⌂</span><span class="nav-label">Overview</span></a>
            <a class="nav-item {{ 'is-active' if active_page == 'orders' else '' }}" href="{{ url_for('orders') }}" {% if active_page == 'orders' %}aria-current="page"{% endif %}><span class="nav-icon" aria-hidden="true">▤</span><span class="nav-label">Orders</span></a>
            <a class="nav-item" href="{{ url_for('products') }}"><span class="nav-icon" aria-hidden="true">✳</span><span class="nav-label">Shop sweets</span></a>
            <p class="sidebar-group sidebar-label">Personal</p>
            <a class="nav-item {{ 'is-active' if active_page == 'profile' else '' }}" href="{{ url_for('profile') }}" {% if active_page == 'profile' %}aria-current="page"{% endif %}><span class="nav-icon" aria-hidden="true">◉</span><span class="nav-label">My profile</span></a>
            <a class="nav-item {{ 'is-active' if active_page == 'settings' else '' }}" href="{{ url_for('settings') }}" {% if active_page == 'settings' %}aria-current="page"{% endif %}><span class="nav-icon" aria-hidden="true">⚙</span><span class="nav-label">Settings</span></a>
        </nav>
        <a href="{{ url_for('home') }}" class="sidebar-shop-link"><span aria-hidden="true">←</span><span class="nav-label">Back to the shop</span></a>
    </aside>
    <button class="sidebar-backdrop" type="button" data-sidebar-backdrop aria-label="Close navigation"></button>
    <div class="account-main">
        <header class="dashboard-topbar">
            <button type="button" class="mobile-menu-trigger" data-sidebar-open aria-label="Open navigation"><span aria-hidden="true">☰</span></button>
            <nav class="breadcrumbs" aria-label="Breadcrumb"><a href="{{ url_for('dashboard') }}">Account</a><span aria-hidden="true">/</span><strong>{{ page_title }}</strong></nav>
            <div class="topbar-actions">
                <details class="topbar-search"><summary data-command-open aria-haspopup="dialog" aria-expanded="false" aria-label="Search the shop">⌕</summary><form action="{{ url_for('products') }}" method="get"><input type="search" name="q" placeholder="Search the shop" aria-label="Search products"><button type="submit" aria-label="Submit search">Search</button></form></details>
                <details class="topbar-notifications"><summary aria-label="Notifications">♧{% if notification_count %}<span class="notification-badge">{{ notification_count }}</span>{% endif %}</summary><div class="topbar-popover"><strong>Updates</strong><p>{{ notification_count }} order{{ '' if notification_count == 1 else 's' }} need your attention.</p><a href="{{ url_for('orders') }}">View orders</a></div></details>
                <details class="topbar-user"><summary><span class="account-avatar small-avatar">{{ current_user.username[:1]|upper }}</span><span class="user-menu-name">{{ current_user.username }}</span><span aria-hidden="true">⌄</span></summary><div class="topbar-popover"><a href="{{ url_for('profile') }}">Profile</a><a href="{{ url_for('settings') }}">Settings</a><a href="{{ url_for('logout') }}">Sign out</a></div></details>
            </div>
        </header>
        <main class="account-content">
            {% with messages = get_flashed_messages() %}{% if messages %}<div class="account-flashes" role="status">{% for message in messages %}<p>{{ message }}</p>{% endfor %}</div>{% endif %}{% endwith %}
            {{ content | safe }}
        </main>
        <footer class="account-footer"><span>Jai Hanuman Sweets</span><a href="mailto:hello@jaihanumansweets.in">Need help?</a></footer>
    </div>
    <nav class="mobile-bottom-nav" aria-label="Account shortcuts"><a class="{{ 'is-active' if active_page == 'dashboard' else '' }}" href="{{ url_for('dashboard') }}"><span aria-hidden="true">⌂</span><small>Home</small></a><a class="{{ 'is-active' if active_page == 'orders' else '' }}" href="{{ url_for('orders') }}"><span aria-hidden="true">▤</span><small>Orders</small></a><a href="{{ url_for('products') }}"><span aria-hidden="true">✳</span><small>Shop</small></a><a class="{{ 'is-active' if active_page == 'profile' else '' }}" href="{{ url_for('profile') }}"><span aria-hidden="true">◉</span><small>Profile</small></a><a class="{{ 'is-active' if active_page == 'settings' else '' }}" href="{{ url_for('settings') }}"><span aria-hidden="true">⚙</span><small>Settings</small></a></nav>
</div><script src="{{ url_for('static', filename='js/main.js') }}" defer></script></body></html>
"""

DASHBOARD_CONTENT = """
<section class="page-heading-row"><div><p class="eyebrow">Your sweet corner</p><h1>Good {{ greeting }}, {{ current_user.username.split(' ')[0] }}.</h1><p>Here’s what’s happening with your orders and favourites.</p></div><a href="{{ url_for('products') }}" class="btn btn-primary">Browse sweets <span aria-hidden="true">→</span></a></section>
<section class="account-stat-grid" aria-label="Account summary"><article class="account-stat"><span class="stat-symbol">▤</span><span class="stat-label">Orders placed</span><strong>{{ order_count }}</strong><small>Since you joined</small></article><article class="account-stat stat-blue"><span class="stat-symbol">₹</span><span class="stat-label">Total spent</span><strong>₹{{ '%.0f'|format(total_spent) }}</strong><small>Across all orders</small></article><article class="account-stat stat-yellow"><span class="stat-symbol">◷</span><span class="stat-label">In your basket</span><strong>{{ cart_count }}</strong><small>Delicious choices</small></article><article class="account-stat stat-green"><span class="stat-symbol">✳</span><span class="stat-label">Member since</span><strong>{{ current_user.created_at.strftime('%b %Y') if current_user.created_at else 'Today' }}</strong><small>Welcome to the family</small></article></section>
<section class="dashboard-columns"><div class="dashboard-section paper-panel"><div class="section-heading-inline"><div><p class="eyebrow">Recently</p><h2>Latest orders</h2></div><a href="{{ url_for('orders') }}">All orders <span aria-hidden="true">→</span></a></div>
{% if recent_orders %}<div class="order-list">{% for order in recent_orders %}<a class="order-row" href="{{ url_for('orders') }}"><span class="order-mark">{{ '%02d'|format(loop.index) }}</span><span class="order-description"><strong>Order #{{ order.id }}</strong><small>{{ order.created_at.strftime('%b %d, %Y') if order.created_at else 'Recently' }} · {{ order.items|length }} item{{ '' if order.items|length == 1 else 's' }}</small></span><span class="order-total">₹{{ '%.2f'|format(order.total) }}</span><span class="status-pill status-{{ order.status|lower }}">{{ order.status|replace('_',' ')|title }}</span></a>{% endfor %}</div>{% else %}<div class="account-empty"><span aria-hidden="true">✳</span><h3>Your first treat is waiting</h3><p>Once you place an order, it will show up here.</p><a href="{{ url_for('products') }}" class="text-link">Explore the collection →</a></div>{% endif %}</div>
<aside class="dashboard-section dashboard-aside"><p class="eyebrow">A little note</p><h2>Made for sharing.</h2><p>Fresh batches, thoughtful ingredients, and a box worth bringing to the table.</p><a href="{{ url_for('products') }}" class="dashboard-note-link">Find something lovely <span aria-hidden="true">↗</span></a><div class="note-stamp" aria-hidden="true">FRESH<br>DAILY</div></aside></section>
<section class="dashboard-section picks-section"><div class="section-heading-inline"><div><p class="eyebrow">Picked for you</p><h2>Popular from our kitchen</h2></div><a href="{{ url_for('products') }}">Shop all <span aria-hidden="true">→</span></a></div><div class="dashboard-picks" data-stagger="grid" data-stagger-direction="up">{% for product in featured_products %}<a class="dashboard-pick" href="{{ url_for('product_detail', product_id=product.id) }}"><img src="{{ product.image or '' }}" alt=""><span>{{ product.category }}</span><strong>{{ product.name }}</strong><small>₹{{ '%.2f'|format(product.price) }}</small></a>{% endfor %}</div></section>
"""

ORDERS_CONTENT = """
<section class="page-heading-row"><div><p class="eyebrow">Your account</p><h1>Order history</h1><p>Every box of something lovely, all in one place.</p></div><a href="{{ url_for('products') }}" class="btn btn-primary">Shop again</a></section>
<section class="dashboard-section paper-panel orders-panel">{% if orders %}<div class="order-list">{% for order in orders %}<article class="order-row order-history-row"><span class="order-mark">#{{ order.id }}</span><span class="order-description"><strong>{{ order.created_at.strftime('%B %d, %Y') if order.created_at else 'Order' }}</strong><small>{{ order.items|length }} item{{ '' if order.items|length == 1 else 's' }} · {{ order.items|map(attribute='product.name')|join(', ') }}</small></span><span class="order-total">₹{{ '%.2f'|format(order.total) }}</span><span class="status-pill status-{{ order.status|lower }}">{{ order.status|replace('_',' ')|title }}</span></article>{% endfor %}</div>{% else %}<div class="account-empty"><span aria-hidden="true">▤</span><h2>No orders yet</h2><p>Your order history will appear here after your first checkout.</p><a href="{{ url_for('products') }}" class="btn btn-primary">Browse sweets</a></div>{% endif %}</section>
"""

PROFILE_CONTENT = """
<section class="profile-cover"><div class="profile-cover-pattern" aria-hidden="true"></div><span class="profile-cover-note">A life made a little sweeter</span></section>
<section class="profile-heading"><div class="account-avatar profile-avatar">{{ current_user.username[:1]|upper }}</div><div class="profile-identity"><h1>{{ current_user.username }}</h1><p>{{ profile.bio or 'Mithai lover and Jai Hanuman Sweets member.' }}</p><span>{{ profile.location or 'A friend of good sweets' }}</span></div><div class="profile-actions"><a href="#edit-profile" class="btn btn-secondary">Edit profile</a><button type="button" class="btn btn-secondary" data-share-profile>Share</button><a href="{{ url_for('settings') }}" class="btn btn-secondary" aria-label="Settings">⚙</a></div></section>
<section class="profile-stats"><div><strong>{{ order_count }}</strong><span>Orders</span></div><div><strong>₹{{ '%.0f'|format(total_spent) }}</strong><span>Spent with us</span></div><div><strong>{{ profile.favorite_category or 'Traditional Sweets' }}</strong><span>Favourite shelf</span></div></section>
<nav class="profile-tabs" aria-label="Profile sections"><a href="#orders">Orders</a><a href="#highlights">Highlights</a><a href="#activity">Activity</a><a href="#about">About</a></nav>
<div class="profile-layout"><div class="profile-main-column"><section class="paper-panel profile-panel" id="orders"><p class="eyebrow">Recent visits to our kitchen</p><h2>Orders</h2>{% if recent_orders %}<div class="order-list">{% for order in recent_orders %}<div class="order-row"><span class="order-mark">#{{ order.id }}</span><span class="order-description"><strong>{{ order.created_at.strftime('%b %d, %Y') if order.created_at else 'Order' }}</strong><small>{{ order.items|length }} item{{ '' if order.items|length == 1 else 's' }}</small></span><span class="order-total">₹{{ '%.2f'|format(order.total) }}</span></div>{% endfor %}</div>{% else %}<p>No orders yet. Your first visit is one click away.</p>{% endif %}</section><section class="paper-panel profile-panel" id="highlights"><p class="eyebrow">Your shelf</p><h2>Favourite category</h2><p>{{ profile.favorite_category or 'Traditional Sweets' }} <a href="{{ url_for('onboarding', edit=1) }}">Update preferences →</a></p></section><section class="paper-panel profile-panel" id="activity"><p class="eyebrow">Activity</p><h2>A little timeline</h2><p>Member since {{ current_user.created_at.strftime('%B %Y') if current_user.created_at else 'today' }}. {{ order_count }} order{{ '' if order_count == 1 else 's' }} placed so far.</p></section></div>
<aside class="paper-panel profile-about" id="about"><p class="eyebrow">About you</p><h2>Your details</h2><p>{{ profile.bio or 'Add a short note about yourself.' }}</p><dl><dt>Email</dt><dd>{{ current_user.email }}</dd><dt>Location</dt><dd>{{ profile.location or 'Not added yet' }}</dd></dl><a class="text-link" href="#edit-profile">Edit details</a></aside></div>
<section class="paper-panel profile-edit" id="edit-profile"><p class="eyebrow">Make it yours</p><h2>Edit profile</h2><form method="post" class="profile-form"><label>Display name<input name="username" value="{{ current_user.username }}" required maxlength="80"></label><label>Email<input type="email" name="email" value="{{ current_user.email }}" required maxlength="120"></label><label>Short bio<textarea name="bio" rows="3" maxlength="240">{{ profile.bio }}</textarea></label><label>Location<input name="location" value="{{ profile.location }}" maxlength="120"></label><button class="btn btn-primary" type="submit">Save profile</button></form></section>
"""

SETTINGS_CONTENT = """
<section class="page-heading-row"><div><p class="eyebrow">Your account</p><h1>Settings</h1><p>Choose the updates and notes you would like from us.</p></div><span class="save-status" data-save-status aria-live="polite">All changes saved</span></section>
<div class="settings-layout"><nav class="settings-nav" aria-label="Settings sections"><a href="#notifications" class="is-active">Notifications</a><a href="#preferences">Preferences</a><a href="#account-details">Account</a><a href="#danger-zone">Danger zone</a></nav>
<form method="post" class="settings-form" data-settings-form>
<section class="paper-panel settings-section" id="notifications"><header><h2>Notifications</h2><p>Keep useful order information close at hand.</p></header><label class="toggle-row"><span><strong>Order updates</strong><small>Receive updates when an order is confirmed or ready.</small></span><input type="checkbox" name="order_updates" role="switch" {{ 'checked' if preferences.order_updates else '' }}></label><label class="toggle-row"><span><strong>New from our kitchen</strong><small>Hear about seasonal sweets and fresh batches.</small></span><input type="checkbox" name="product_updates" role="switch" {{ 'checked' if preferences.product_updates else '' }}></label><label class="toggle-row"><span><strong>Occasional newsletter</strong><small>Recipes, festive boxes, and notes from the shop.</small></span><input type="checkbox" name="newsletter" role="switch" {{ 'checked' if preferences.newsletter else '' }}></label></section>
<section class="paper-panel settings-section" id="preferences"><header><h2>Shopping preferences</h2><p>Your favourite shelf helps us make better recommendations.</p></header><label class="settings-field">Favourite category<select name="favorite_category">{% for category in categories %}<option value="{{ category }}" {{ 'selected' if profile.favorite_category == category else '' }}>{{ category }}</option>{% endfor %}</select></label></section>
<section class="paper-panel settings-section" id="account-details"><header><h2>Account details</h2><p>These details are used for orders and account support.</p></header><p><strong>{{ current_user.username }}</strong><br><span>{{ current_user.email }}</span></p><a href="{{ url_for('profile') }}#edit-profile" class="text-link">Edit profile details →</a></section>
<section class="paper-panel settings-section danger-zone" id="danger-zone"><header><h2>Delete account</h2><p>Remove your profile and account preferences. This cannot be undone.</p></header><button type="button" class="btn danger-button" data-delete-account>Delete my account</button></section>
<div class="sticky-save-bar" data-save-bar hidden><span data-save-bar-message>You have unsaved changes</span><button type="button" class="btn btn-secondary" data-discard-settings>Discard</button><button type="submit" class="btn btn-primary" data-save-settings>Save changes</button></div>
</form></div>
<dialog class="confirm-dialog" data-delete-dialog><form method="post" action="{{ url_for('delete_account') }}"><p class="eyebrow">Please confirm</p><h2>Delete your account?</h2><p>Your profile, preferences, and order history will be removed from this account.</p><div class="dialog-actions"><button type="button" class="btn btn-secondary" data-close-delete>Keep account</button><button type="submit" class="btn danger-button">Delete account</button></div></form></dialog>
"""

ONBOARDING_CONTENT = """
<main class="onboarding-page"><a href="{{ url_for('home') }}" class="brand"><span class="brand-mark">J</span><span>Jai Hanuman<br><small>Sweets</small></span></a><section class="onboarding-panel">
<div class="onboarding-progress" aria-label="Step {{ step }} of 3">{% for label in ['Your taste','Your updates','All set'] %}<div class="progress-step {{ 'is-complete' if loop.index < step else '' }} {{ 'is-current' if loop.index == step else '' }}"><span>{{ '✓' if loop.index < step else loop.index }}</span><small>{{ label }}</small></div>{% endfor %}<div class="progress-line"><span style="width: {{ (step - 1) * 50 }}%"></span></div></div>
<p class="eyebrow">A few quick details</p>
{% if step == 1 %}<h1>What do you reach for first?</h1><p>We’ll use this to make your account feel more like yours.</p><form method="post" class="onboarding-form"><div class="choice-grid">{% for category in categories %}<label class="choice-card"><input type="radio" name="favorite_category" value="{{ category }}" {{ 'checked' if favorite_category == category else '' }}><span class="choice-check">✓</span><strong>{{ category }}</strong><small>{{ ['Classic mithai for every celebration','Soft, milky favourites','A thoughtful gift in every box','Savory bites for tea time'][loop.index0] }}</small></label>{% endfor %}</div><div class="onboarding-actions"><button name="action" value="skip" class="text-button" type="submit">Skip for now</button><button name="action" value="next" class="btn btn-primary" type="submit">Continue →</button></div></form>
{% elif step == 2 %}<h1>How should we keep in touch?</h1><p>Choose the notes that are useful. You can change these any time.</p><form method="post" class="onboarding-form"><label class="toggle-row"><span><strong>Order updates</strong><small>Helpful notes as your order moves along.</small></span><input type="checkbox" name="order_updates" {{ 'checked' if order_updates else '' }}></label><label class="toggle-row"><span><strong>Seasonal favourites</strong><small>Occasional news about new sweets and festive boxes.</small></span><input type="checkbox" name="newsletter" {{ 'checked' if newsletter else '' }}></label><div class="onboarding-actions"><button name="action" value="back" class="text-button" type="submit">← Back</button><button name="action" value="next" class="btn btn-primary" type="submit">Continue →</button></div></form>
{% else %}<div class="onboarding-success" aria-hidden="true">✳</div><h1>Your sweet corner is ready.</h1><p>We’ll keep your {{ favorite_category }} favourites close and share only the updates you chose.</p><form method="post" class="onboarding-actions"><button name="action" value="back" class="text-button" type="submit">← Back</button><button name="action" value="finish" class="btn btn-primary" type="submit">Go to my account →</button></form>{% endif %}
</section><form method="post" class="onboarding-skip-form"><button type="submit" name="action" value="skip" class="onboarding-skip">Skip setup</button></form></main>
"""

ERROR_PAGE_HTML = """
<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>{{ error_code }} | Jai Hanuman Sweets</title><link rel="stylesheet" href="{{ url_for('static', filename='css/style.css') }}"></head><body class="error-page"><main class="error-content"><a class="brand" href="{{ url_for('home') }}"><span class="brand-mark">J</span><span>Jai Hanuman<br><small>Sweets</small></span></a><div class="error-paper"><span class="error-code">{{ error_code }}</span><p class="eyebrow">A small detour</p><h1>{{ error_title }}</h1><p>{{ error_message }}</p><div class="error-actions"><a href="{{ url_for('home') }}" class="btn btn-primary">Go to homepage</a><a href="{{ url_for('products') }}" class="btn btn-secondary">Browse sweets</a></div></div><p class="error-help">Need a hand? <a href="mailto:hello@jaihanumansweets.in">Contact customer care</a></p></main></body></html>
"""


def get_cart_items_for_user(user_id):
    return CartItem.query.filter_by(user_id=user_id).all()


def get_cart_total(user_id):
    items = get_cart_items_for_user(user_id)
    return sum(item.product.price * item.quantity for item in items)


@app.route("/")
def home():
    products = Product.query.order_by(Product.id).limit(3).all()
    rating_rows = db.session.query(ProductReview.product_id, db.func.avg(ProductReview.rating), db.func.count(ProductReview.id)).group_by(ProductReview.product_id).all()
    ratings = {product_id: (average, count) for product_id, average, count in rating_rows}
    content = render_template_string(
        HOME_HTML,
        products=products,
        ratings=ratings,
        total_orders=Order.query.count(),
        product_count=Product.query.count(),
    )
    return render_template_string(BASE_HTML, title="Sweet Shop", content=content)


@app.route("/about")
def about():
    return render_template_string(BASE_HTML, title="Our story", content=render_template_string(ABOUT_HTML))


@app.route("/products")
def products():
    search = request.args.get("q", "").strip()
    selected_categories = request.args.getlist("category")
    category_rows = db.session.query(Product.category, db.func.count(Product.id)).group_by(Product.category).all()
    categories = [(name, count) for name, count in category_rows]
    absolute_min = db.session.query(db.func.min(Product.price)).scalar() or 0
    absolute_max = db.session.query(db.func.max(Product.price)).scalar() or 1000
    try:
        min_price = float(request.args.get("min_price", absolute_min))
        max_price = float(request.args.get("max_price", absolute_max))
    except (TypeError, ValueError):
        min_price, max_price = absolute_min, absolute_max
    min_price = min(max(min_price, absolute_min), absolute_max)
    max_price = min(max(max_price, absolute_min), absolute_max)
    if min_price > max_price:
        min_price, max_price = max_price, min_price
    in_stock = request.args.get("in_stock") == "1"
    sort = request.args.get("sort", "relevance")
    if sort not in {"relevance", "price_asc", "price_desc", "newest", "rating"}:
        sort = "relevance"
    query = Product.query.filter(Product.price >= min_price, Product.price <= max_price)
    if search:
        pattern = f"%{search}%"
        query = query.filter(db.or_(Product.name.ilike(pattern), Product.category.ilike(pattern), Product.description.ilike(pattern)))
    if selected_categories:
        query = query.filter(Product.category.in_(selected_categories))
    if in_stock:
        query = query.filter(Product.stock > 0)

    rating_rows = db.session.query(
        ProductReview.product_id,
        db.func.avg(ProductReview.rating),
        db.func.count(ProductReview.id),
    ).group_by(ProductReview.product_id).all()
    ratings = {product_id: (average, count) for product_id, average, count in rating_rows}
    all_products = query.all()
    if sort == "price_asc":
        all_products.sort(key=lambda product: (product.price, product.name.lower()))
    elif sort == "price_desc":
        all_products.sort(key=lambda product: (-product.price, product.name.lower()))
    elif sort == "newest":
        all_products.sort(key=lambda product: product.id, reverse=True)
    elif sort == "rating":
        all_products.sort(key=lambda product: (-(ratings.get(product.id, (0, 0))[0] or 0), product.name.lower()))
    elif search:
        all_products.sort(key=lambda product: (not product.name.lower().startswith(search.lower()), product.name.lower()))
    total_results = len(all_products)
    page_size = 9
    page_count = max(1, (total_results + page_size - 1) // page_size)
    try:
        page = min(max(int(request.args.get("page", 1)), 1), page_count)
    except (TypeError, ValueError):
        page = 1
    first_result = (page - 1) * page_size + 1 if total_results else 0
    last_result = min(page * page_size, total_results)
    wishlist_ids = set()
    if current_user.is_authenticated:
        wishlist_ids = {row.product_id for row in WishlistItem.query.filter_by(user_id=current_user.id).all()}
    filter_args = request.args.to_dict(flat=False)
    filter_args.pop("page", None)
    view_args = dict(filter_args)
    view_args.pop("view", None)
    view = request.args.get("view", "grid")
    if view not in {"grid", "list"}:
        view = "grid"
    content = render_template_string(
        PRODUCTS_HTML,
        products=all_products[(page - 1) * page_size:page * page_size],
        search=search,
        categories=categories,
        selected_categories=selected_categories,
        absolute_min=absolute_min,
        absolute_max=absolute_max,
        min_price=min_price,
        max_price=max_price,
        in_stock=in_stock,
        available_count=Product.query.filter(Product.stock > 0).count(),
        sort=sort,
        view=view,
        ratings=ratings,
        wishlist_ids=wishlist_ids,
        first_result=first_result,
        last_result=last_result,
        total_results=total_results,
        page=page,
        page_count=page_count,
        filter_args=filter_args,
        view_args=view_args,
    )
    return render_template_string(BASE_HTML, title="Products", content=content)


@app.route("/api/search")
def global_search():
    term = request.args.get("q", "").strip()[:80]
    results = []

    def add_group(label, items):
        if items:
            results.append({"label": label, "items": items})

    pages = [
        ("Home", url_for("home"), "Shop landing page"),
        ("Shop sweets", url_for("products"), "Browse the full collection"),
        ("Gifting", url_for("pricing"), "Prices and bulk gifting"),
        ("Our story", url_for("about"), "About Jai Hanuman Sweets"),
        ("Frequently asked questions", url_for("faq"), "Ordering and delivery help"),
    ]
    normalized = term.casefold()
    page_items = [
        {"title": title, "href": href, "detail": detail, "icon": "↗", "kind": "page"}
        for title, href, detail in pages
        if not normalized or normalized in title.casefold() or normalized in detail.casefold()
    ]
    if current_user.is_authenticated:
        account_pages = [
            ("My overview", url_for("dashboard"), "Your account dashboard"),
            ("My orders", url_for("orders"), "Order history and status"),
            ("My profile", url_for("profile"), "Edit your profile"),
            ("Account settings", url_for("settings"), "Notifications and preferences"),
            ("Saved sweets", url_for("wishlist"), "Your wishlist"),
        ]
        page_items.extend(
            {"title": title, "href": href, "detail": detail, "icon": "◉", "kind": "page"}
            for title, href, detail in account_pages
            if not normalized or normalized in title.casefold() or normalized in detail.casefold()
        )
    add_group("Pages", page_items[:7])

    actions = []
    if current_user.is_authenticated:
        actions.extend([
            {"title": "Open basket", "href": url_for("cart"), "detail": "Review your sweets", "icon": "🛒", "kind": "action"},
            {"title": "Continue checkout", "href": url_for("checkout"), "detail": "Choose delivery and payment", "icon": "→", "kind": "action"},
        ])
    actions = [item for item in actions if not normalized or normalized in item["title"].casefold() or normalized in item["detail"].casefold()]
    add_group("Quick actions", actions)

    if term:
        pattern = f"%{term}%"
        products_found = Product.query.filter(db.or_(
            Product.name.ilike(pattern),
            Product.category.ilike(pattern),
            Product.description.ilike(pattern),
        )).order_by(Product.name).limit(6).all()
        add_group("Products", [
            {"title": product.name, "href": url_for("product_detail", product_id=product.id), "detail": f"{product.category} · ₹{product.price:.2f}", "icon": "✳", "kind": "product"}
            for product in products_found
        ])

        category_rows = db.session.query(Product.category, db.func.count(Product.id)).filter(
            Product.category.ilike(pattern)
        ).group_by(Product.category).limit(4).all()
        add_group("Categories", [
            {"title": category, "href": url_for("products", category=category), "detail": f"{count} products", "icon": "▦", "kind": "category"}
            for category, count in category_rows
        ])

        if current_user.is_authenticated:
            is_admin = current_user.email.strip().lower() in current_app.config["ADMIN_EMAILS"] or (current_user.access and current_user.access.role == "admin")
            order_query = Order.query.join(User)
            if not is_admin:
                order_query = order_query.filter(Order.user_id == current_user.id)
            order_query = order_query.filter(db.or_(
                Order.status.ilike(pattern),
                User.username.ilike(pattern),
                User.email.ilike(pattern),
            ))
            if term.isdigit():
                order_query = order_query.union(Order.query.filter_by(id=int(term)))
                if not is_admin:
                    order_query = Order.query.join(User).filter(Order.user_id == current_user.id, Order.id == int(term))
            orders_found = order_query.order_by(Order.created_at.desc()).limit(5).all()
            add_group("Orders", [
                {"title": f"Order #{order.id}", "href": url_for("orders") if not is_admin else url_for("admin_tools", order=order.id), "detail": f"{order.status.title()} · ₹{order.total:.2f}", "icon": "▤", "kind": "order"}
                for order in orders_found
            ])

            if is_admin:
                users_found = User.query.filter(
                    User.id != current_user.id,
                    db.or_(User.username.ilike(pattern), User.email.ilike(pattern)),
                ).order_by(User.username).limit(5).all()
                add_group("Customers", [
                    {"title": user.username, "href": url_for("admin_user_detail", user_id=user.id), "detail": user.email, "icon": "◉", "kind": "user"}
                    for user in users_found
                ])

    return jsonify(query=term, groups=results)


@app.route("/products/<int:product_id>")
def product_detail(product_id):
    product = Product.query.get_or_404(product_id)
    reviews = ProductReview.query.filter_by(product_id=product.id).order_by(ProductReview.created_at.desc()).all()
    rating_average = sum(review.rating for review in reviews) / len(reviews) if reviews else 0
    is_wishlisted = current_user.is_authenticated and WishlistItem.query.filter_by(user_id=current_user.id, product_id=product.id).first() is not None
    related_products = Product.query.filter(Product.category == product.category, Product.id != product.id).limit(4).all()
    if len(related_products) < 4:
        extra_products = Product.query.filter(Product.id != product.id, Product.id.notin_([item.id for item in related_products])).limit(4 - len(related_products)).all()
        related_products.extend(extra_products)
    content = render_template_string(
        PRODUCT_DETAIL_HTML,
        product=product,
        reviews=reviews,
        review_count=len(reviews),
        rating_average=rating_average,
        related_products=related_products,
        is_wishlisted=is_wishlisted,
    )
    return render_template_string(BASE_HTML, title=product.name, content=content)


@app.route("/products/<int:product_id>/reviews", methods=["POST"])
@login_required
def add_review(product_id):
    product = Product.query.get_or_404(product_id)
    try:
        rating = int(request.form.get("rating", ""))
    except ValueError:
        rating = 0
    body = request.form.get("body", "").strip()
    if rating not in range(1, 6) or not body:
        flash("Choose a star rating and add a short review.")
    elif ProductReview.query.filter_by(user_id=current_user.id, product_id=product.id).first():
        flash("You have already reviewed this sweet.")
    else:
        db.session.add(ProductReview(user_id=current_user.id, product_id=product.id, rating=rating, body=body[:1000]))
        db.session.commit()
        flash("Thank you for sharing your review.")
    return redirect(url_for("product_detail", product_id=product.id) + "#reviews")


@app.route("/wishlist/toggle/<int:product_id>", methods=["POST"])
@login_required
def toggle_wishlist(product_id):
    Product.query.get_or_404(product_id)
    item = WishlistItem.query.filter_by(user_id=current_user.id, product_id=product_id).first()
    if item:
        db.session.delete(item)
        flash("Removed from your saved sweets.")
    else:
        db.session.add(WishlistItem(user_id=current_user.id, product_id=product_id))
        flash("Saved to your wishlist.")
    db.session.commit()
    destination = request.form.get("next", "")
    if destination.startswith("/") and not destination.startswith("//"):
        return redirect(destination)
    return redirect(url_for("product_detail", product_id=product_id))


SWEET_CATEGORIES = ["Traditional Sweets", "Milk Sweets", "Gift Boxes", "Snacks & Savouries"]


def render_account_page(page_title, active_page, content, **context):
    notification_count = Order.query.filter_by(user_id=current_user.id, status="pending").count()
    return render_template_string(
        ACCOUNT_SHELL,
        page_title=page_title,
        active_page=active_page,
        notification_count=notification_count,
        content=content,
        **context,
    )


@app.route("/dashboard")
@login_required
def dashboard():
    orders = Order.query.filter_by(user_id=current_user.id).order_by(Order.created_at.desc()).all()
    cart_count = sum(item.quantity for item in get_cart_items_for_user(current_user.id))
    hour = datetime.now().hour
    greeting = "morning" if hour < 12 else "afternoon" if hour < 18 else "evening"
    content = render_template_string(
        DASHBOARD_CONTENT,
        greeting=greeting,
        order_count=len(orders),
        total_spent=sum(order.total for order in orders),
        cart_count=cart_count,
        recent_orders=orders[:5],
        featured_products=Product.query.order_by(Product.id).limit(4).all(),
    )
    return render_account_page("Overview", "dashboard", content)


@app.route("/orders")
@login_required
def orders():
    user_orders = Order.query.filter_by(user_id=current_user.id).order_by(Order.created_at.desc()).all()
    content = render_template_string(ORDERS_CONTENT, orders=user_orders)
    return render_account_page("Orders", "orders", content)


@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    profile_data = current_user.profile
    if profile_data is None:
        profile_data = CustomerProfile(user=current_user)
        db.session.add(profile_data)

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        duplicate = User.query.filter(
            User.id != current_user.id,
            (User.username == username) | (User.email == email),
        ).first()
        if not username or not email or duplicate:
            flash("Please enter a name and email that are not already in use.")
        else:
            current_user.username = username
            current_user.email = email
            profile_data.bio = request.form.get("bio", "").strip()[:240]
            profile_data.location = request.form.get("location", "").strip()[:120]
            db.session.commit()
            flash("Your profile has been updated.")
            return redirect(url_for("profile"))

    user_orders = Order.query.filter_by(user_id=current_user.id).order_by(Order.created_at.desc()).all()
    content = render_template_string(
        PROFILE_CONTENT,
        profile=profile_data,
        recent_orders=user_orders[:5],
        order_count=len(user_orders),
        total_spent=sum(order.total for order in user_orders),
    )
    db.session.commit()
    return render_account_page("Profile", "profile", content)


@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    preferences = current_user.preferences
    if preferences is None:
        preferences = CustomerSettings(user=current_user)
        db.session.add(preferences)
    profile_data = current_user.profile
    if profile_data is None:
        profile_data = CustomerProfile(user=current_user)
        db.session.add(profile_data)

    if request.method == "POST":
        favorite_category = request.form.get("favorite_category", "Traditional Sweets")
        if favorite_category not in SWEET_CATEGORIES:
            return jsonify(error="Choose a valid category."), 400
        preferences.order_updates = "order_updates" in request.form
        preferences.product_updates = "product_updates" in request.form
        preferences.newsletter = "newsletter" in request.form
        profile_data.favorite_category = favorite_category
        db.session.commit()
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify(saved=True)
        flash("Your settings have been saved.")
        return redirect(url_for("settings"))

    content = render_template_string(
        SETTINGS_CONTENT,
        preferences=preferences,
        profile=profile_data,
        categories=SWEET_CATEGORIES,
    )
    db.session.commit()
    return render_account_page("Settings", "settings", content)


@app.route("/account/delete", methods=["POST"])
@login_required
def delete_account():
    user = current_user._get_current_object()
    logout_user()
    db.session.delete(user)
    db.session.commit()
    flash("Your account has been deleted.")
    return redirect(url_for("home"))


@app.route("/onboarding", methods=["GET", "POST"])
@login_required
def onboarding():
    progress = current_user.onboarding
    if progress is None:
        progress = OnboardingProgress(user=current_user)
        db.session.add(progress)
        db.session.commit()

    editing = request.args.get("edit") == "1"
    if progress.completed and not editing:
        return redirect(url_for("dashboard"))
    if editing and progress.completed:
        progress.step = 1
        progress.completed = False
        db.session.commit()

    if request.method == "POST":
        action = request.form.get("action", "next")
        if action == "skip":
            progress.completed = True
            profile_data = current_user.profile or CustomerProfile(user=current_user)
            db.session.add(profile_data)
            db.session.commit()
            return redirect(url_for("dashboard"))
        if action == "back":
            progress.step = max(1, progress.step - 1)
            db.session.commit()
            return redirect(url_for("onboarding", edit="1" if editing else None))

        if progress.step == 1:
            favorite_category = request.form.get("favorite_category", "")
            if favorite_category not in SWEET_CATEGORIES:
                flash("Choose a category to continue.")
            else:
                progress.favorite_category = favorite_category
                progress.step = 2
        elif progress.step == 2:
            progress.order_updates = "order_updates" in request.form
            progress.newsletter = "newsletter" in request.form
            progress.step = 3
        else:
            profile_data = current_user.profile or CustomerProfile(user=current_user)
            preferences = current_user.preferences or CustomerSettings(user=current_user)
            profile_data.favorite_category = progress.favorite_category
            preferences.order_updates = progress.order_updates
            preferences.newsletter = progress.newsletter
            progress.completed = True
            db.session.add_all([profile_data, preferences])
            db.session.commit()
            flash("Your account is ready. Welcome to the family!")
            return redirect(url_for("dashboard"))
        db.session.commit()
        return redirect(url_for("onboarding", edit="1" if editing else None))

    content = render_template_string(
        ONBOARDING_CONTENT,
        step=progress.step,
        categories=SWEET_CATEGORIES,
        favorite_category=progress.favorite_category,
        order_updates=progress.order_updates,
        newsletter=progress.newsletter,
    )
    return render_template_string(AUTH_SHELL, title="Getting started", content=content)


@app.route("/maintenance")
def maintenance():
    content = """
    <main class="maintenance-page"><a class="brand" href="{{ url_for('home') }}"><span class="brand-mark">J</span><span>Jai Hanuman<br><small>Sweets</small></span></a><section class="paper-panel"><p class="eyebrow">A little pause</p><h1>We’re preparing something fresh.</h1><p>The shop is taking a short maintenance break. Please check back soon or contact us for help with an existing order.</p><a class="btn btn-primary" href="{{ url_for('home') }}">Try the shop again</a><a class="text-link" href="mailto:hello@jaihanumansweets.in">Contact customer care</a></section></main>
    """
    return render_template_string(AUTH_SHELL, title="Back soon", content=render_template_string(content))


def admin_required(view_function):
    @login_required
    @wraps(view_function)
    def guarded_view(*args, **kwargs):
        allowed_email = current_user.email.strip().lower() in current_app.config["ADMIN_EMAILS"]
        assigned_admin = current_user.access is not None and current_user.access.role == "admin"
        if not allowed_email and not assigned_admin:
            abort(403)
        return view_function(*args, **kwargs)
    return guarded_view


def access_for(user):
    if user.access:
        return user.access
    return UserAccess(role="admin" if user.email.strip().lower() in current_app.config["ADMIN_EMAILS"] else "customer")


def log_admin_action(action, resource_type, resource_id="", details=""):
    request_context = f"IP {request.remote_addr or 'unknown'} · UA {request.user_agent.string[:200]}"
    full_details = f"{details} · {request_context}" if details else request_context
    db.session.add(AuditLog(
        actor_id=current_user.id,
        actor_name=current_user.username,
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id),
        details=full_details,
    ))


def period_value():
    try:
        days = int(request.args.get("days", 7))
    except ValueError:
        days = 7
    return days if days in {7, 30, 90} else 7


def customer_query():
    query = User.query.outerjoin(UserAccess).filter(db.or_(UserAccess.id.is_(None), UserAccess.role == "customer"))
    admin_emails = current_app.config["ADMIN_EMAILS"]
    if admin_emails:
        query = query.filter(db.func.lower(User.email).notin_(admin_emails))
    return query


def order_metrics(days):
    start = datetime.utcnow() - timedelta(days=days)
    orders_in_period = Order.query.filter(Order.created_at >= start).all()
    revenue = sum(order.total for order in orders_in_period if order.status != "cancelled")
    order_count = sum(1 for order in orders_in_period if order.status != "cancelled")
    customers = customer_query().filter(User.created_at >= start).count()
    low_stock_products = Product.query.filter(Product.stock <= 5).order_by(Product.stock.asc()).limit(5).all()
    by_day = {}
    for order in orders_in_period:
        if order.status != "cancelled":
            key = order.created_at.date()
            by_day[key] = by_day.get(key, 0) + order.total
    chart_step = max(1, (days + 12) // 13)
    period_start = (datetime.utcnow() - timedelta(days=days - 1)).date()
    buckets = {}
    for day, amount in by_day.items():
        bucket_index = max(0, (day - period_start).days // chart_step)
        buckets[bucket_index] = buckets.get(bucket_index, 0) + amount
    chart_data = []
    for bucket_index in range((days + chart_step - 1) // chart_step):
        bucket_day = period_start + timedelta(days=bucket_index * chart_step)
        chart_data.append({"day": bucket_day.strftime("%d %b"), "amount": buckets.get(bucket_index, 0)})
    peak = max((point["amount"] for point in chart_data), default=0)
    for point in chart_data:
        point["height"] = max(4, int(point["amount"] / peak * 100)) if peak else 4
    return {
        "orders": orders_in_period,
        "revenue": revenue,
        "order_count": order_count,
        "average_order": revenue / order_count if order_count else 0,
        "new_customers": customers,
        "low_stock_products": low_stock_products,
        "low_stock": Product.query.filter(Product.stock <= 5).count(),
        "chart_data": chart_data,
    }


@app.route("/admin")
@admin_required
def admin_dashboard():
    days = period_value()
    metrics = order_metrics(days)
    content = render_template_string(
        ADMIN_DASHBOARD_HTML,
        selected_period=days,
        customer_count=customer_query().count(),
        recent_activity=AuditLog.query.order_by(AuditLog.created_at.desc()).limit(6).all(),
        **metrics,
    )
    return render_template_string(ADMIN_SHELL, page_title="Overview", active="dashboard", content=content)


@app.route("/admin/users")
@admin_required
def admin_users():
    search = request.args.get("q", "").strip()
    role_filter = request.args.get("role", "")
    status_filter = request.args.get("status", "")
    sort = request.args.get("sort", "name")
    direction = request.args.get("dir", "asc")
    if role_filter not in {"", "customer", "staff", "admin"}:
        role_filter = ""
    if status_filter not in {"", "active", "suspended"}:
        status_filter = ""
    try:
        per_page = int(request.args.get("per_page", 25))
    except ValueError:
        per_page = 25
    if per_page not in {25, 50, 100}:
        per_page = 25
    entries = []
    for user in User.query.all():
        access = access_for(user)
        if search and search.casefold() not in user.username.casefold() and search.casefold() not in user.email.casefold():
            continue
        if role_filter and access.role != role_filter:
            continue
        if status_filter and access.status != status_filter:
            continue
        entries.append((user, access))
    if sort == "name":
        entries.sort(key=lambda entry: entry[0].username.casefold(), reverse=direction == "desc")
    else:
        entries.sort(key=lambda entry: entry[0].created_at or datetime.min, reverse=direction == "desc")
    total_users = len(entries)
    try:
        page = max(1, int(request.args.get("page", 1)))
    except ValueError:
        page = 1
    pages = max(1, (total_users + per_page - 1) // per_page)
    page = min(page, pages)
    first_user = (page - 1) * per_page + 1 if total_users else 0
    last_user = min(page * per_page, total_users)
    content = render_template_string(
        ADMIN_USERS_HTML,
        users=entries[(page - 1) * per_page:page * per_page],
        total_users=total_users,
        search=search,
        role_filter=role_filter,
        status_filter=status_filter,
        sort=sort,
        direction=direction,
        per_page=per_page,
        page=page,
        pages=pages,
        first_user=first_user,
        last_user=last_user,
    )
    return render_template_string(ADMIN_SHELL, page_title="Customers", active="users", content=content)


@app.route("/admin/users.csv")
@admin_required
def admin_users_csv():
    search = request.args.get("q", "").strip().casefold()
    role_filter = request.args.get("role", "")
    status_filter = request.args.get("status", "")
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "name", "email", "role", "status", "created_at", "last_active"])
    for user in User.query.order_by(User.username).all():
        access = access_for(user)
        if search and search not in user.username.casefold() and search not in user.email.casefold():
            continue
        if role_filter and access.role != role_filter:
            continue
        if status_filter and access.status != status_filter:
            continue
        writer.writerow([user.id, user.username, user.email, access.role, access.status, user.created_at, access.last_active])
    return Response(output.getvalue(), mimetype="text/csv", headers={"Content-Disposition": "attachment; filename=customers.csv"})


@app.route("/admin/users/create", methods=["POST"])
@admin_required
def admin_create_user():
    username = request.form.get("username", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    role = request.form.get("role", "customer")
    if not username or not email or len(password) < 12 or role not in {"customer", "staff"}:
        flash("Enter a name, email, 12-character temporary password, and valid role.")
        return redirect(url_for("admin_users"))
    if User.query.filter((User.username == username) | (User.email == email)).first():
        flash("That name or email is already in use.")
        return redirect(url_for("admin_users"))
    user = User(username=username, email=email)
    user.set_password(password)
    user.access = UserAccess(role=role)
    db.session.add(user)
    db.session.flush()
    log_admin_action("created", "User", user.id, f"Created {role} account {username}")
    db.session.commit()
    flash("Account created. Share the temporary password securely.")
    return redirect(url_for("admin_users"))


@app.route("/admin/users/bulk", methods=["POST"])
@admin_required
def admin_bulk_users():
    action = request.form.get("action", "")
    try:
        user_ids = {int(value) for value in request.form.getlist("user_ids")}
    except ValueError:
        user_ids = set()
    if not user_ids or action not in {"activate", "suspend", "delete"}:
        flash("Select users and a valid bulk action.")
        return redirect(url_for("admin_users"))
    affected = 0
    for user in User.query.filter(User.id.in_(user_ids)).all():
        is_allowlisted_admin = user.email.strip().lower() in current_app.config["ADMIN_EMAILS"]
        if user.id == current_user.id or is_allowlisted_admin or access_for(user).role == "admin":
            continue
        if action == "delete":
            log_admin_action("deleted", "User", user.id, f"Bulk delete of {user.username}")
            db.session.delete(user)
        else:
            access = user.access or UserAccess(user=user)
            access.status = action
            db.session.add(access)
            log_admin_action(action, "User", user.id, f"{user.username} account {action}d")
        affected += 1
    db.session.commit()
    flash(f"{affected} account(s) updated.")
    return redirect(url_for("admin_users"))


@app.route("/admin/users/<int:user_id>")
@admin_required
def admin_user_detail(user_id):
    user = User.query.get_or_404(user_id)
    content = render_template_string(
        ADMIN_USER_DETAIL_HTML,
        user=user,
        access=access_for(user),
        orders=Order.query.filter_by(user_id=user.id).order_by(Order.created_at.desc()).all(),
        events=AuditLog.query.filter_by(resource_type="User", resource_id=str(user.id)).order_by(AuditLog.created_at.desc()).limit(12).all(),
    )
    return render_template_string(ADMIN_SHELL, page_title="Account details", active="users", content=content)


@app.route("/admin/users/<int:user_id>/access", methods=["POST"])
@admin_required
def admin_user_access(user_id):
    user = User.query.get_or_404(user_id)
    role = request.form.get("role", "customer")
    status = request.form.get("status", "active")
    if role not in {"customer", "staff"} or status not in {"active", "suspended"}:
        flash("That role or status is not allowed.")
        return redirect(url_for("admin_user_detail", user_id=user.id))
    access = user.access or UserAccess(user=user)
    before = f"{access.role}/{access.status}"
    access.role = role
    access.status = status
    access.last_active = datetime.utcnow()
    db.session.add(access)
    log_admin_action("updated", "User", user.id, f"Access changed from {before} to {role}/{status}")
    db.session.commit()
    flash("Account access updated.")
    return redirect(request.referrer if request.referrer and request.referrer.startswith("/") else url_for("admin_user_detail", user_id=user.id))


@app.route("/admin/analytics")
@admin_required
def admin_analytics():
    days = period_value()
    metrics = order_metrics(days)
    previous_start = datetime.utcnow() - timedelta(days=days * 2)
    previous_end = datetime.utcnow() - timedelta(days=days)
    previous_orders = Order.query.filter(Order.created_at >= previous_start, Order.created_at < previous_end, Order.status != "cancelled").all()
    previous_revenue = sum(order.total for order in previous_orders)
    compare = request.args.get("compare") == "1"
    change_percent = ((metrics["revenue"] - previous_revenue) / previous_revenue * 100) if previous_revenue else (100.0 if metrics["revenue"] else 0.0)
    top_products = db.session.query(Product, db.func.sum(OrderItem.quantity).label("quantity")).join(OrderItem).join(Order).filter(Order.created_at >= datetime.utcnow() - timedelta(days=days), Order.status != "cancelled").group_by(Product.id).order_by(db.desc("quantity")).limit(8).all()
    content = render_template_string(
        ADMIN_ANALYTICS_HTML,
        days=days,
        compare=compare,
        previous_revenue=previous_revenue,
        previous_orders=len(previous_orders),
        change_percent=change_percent,
        top_products=top_products,
        **metrics,
    )
    return render_template_string(ADMIN_SHELL, page_title="Analytics", active="analytics", content=content)


@app.route("/admin/analytics.csv")
@admin_required
def admin_analytics_csv():
    metrics = order_metrics(period_value())
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Order ID", "Customer", "Created", "Status", "Total"])
    for order in metrics["orders"]:
        writer.writerow([order.id, order.user.username, order.created_at, order.status, f"{order.total:.2f}"])
    return Response(output.getvalue(), mimetype="text/csv", headers={"Content-Disposition": "attachment; filename=shop-analytics.csv"})


@app.route("/admin/audit")
@admin_required
def admin_audit():
    search = request.args.get("q", "").strip()
    action_filter = request.args.get("action", "")
    resource_filter = request.args.get("resource", "")
    query = AuditLog.query.filter(AuditLog.created_at >= datetime.utcnow() - timedelta(days=365))
    if action_filter:
        query = query.filter_by(action=action_filter)
    if resource_filter:
        query = query.filter_by(resource_type=resource_filter)
    if search:
        pattern = f"%{search}%"
        query = query.filter(db.or_(AuditLog.actor_name.ilike(pattern), AuditLog.details.ilike(pattern), AuditLog.resource_id.ilike(pattern)))
    total = query.count()
    entries = query.order_by(AuditLog.created_at.desc()).limit(100).all()
    content = render_template_string(
        ADMIN_AUDIT_HTML,
        search=search,
        action_filter=action_filter,
        resource_filter=resource_filter,
        actions=[row[0] for row in db.session.query(AuditLog.action).distinct().all()],
        resources=[row[0] for row in db.session.query(AuditLog.resource_type).distinct().all()],
        entries=entries,
        total=total,
    )
    return render_template_string(ADMIN_SHELL, page_title="Activity log", active="audit", content=content)


@app.route("/admin/audit.csv")
@admin_required
def admin_audit_csv():
    query = AuditLog.query.filter(AuditLog.created_at >= datetime.utcnow() - timedelta(days=365)).order_by(AuditLog.created_at.desc())
    if request.args.get("action"):
        query = query.filter_by(action=request.args["action"])
    if request.args.get("resource"):
        query = query.filter_by(resource_type=request.args["resource"])
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Timestamp", "Actor", "Action", "Resource", "Resource ID", "Details"])
    for entry in query.limit(10000).all():
        writer.writerow([entry.created_at, entry.actor_name, entry.action, entry.resource_type, entry.resource_id, entry.details])
    return Response(output.getvalue(), mimetype="text/csv", headers={"Content-Disposition": "attachment; filename=audit-log.csv"})


@app.route("/admin/tools")
@admin_required
def admin_tools():
    search = request.args.get("q", "").strip()
    order_query = Order.query.join(User)
    product_query = Product.query
    if search:
        pattern = f"%{search}%"
        order_query = order_query.filter(db.or_(User.username.ilike(pattern), User.email.ilike(pattern)))
        product_query = product_query.filter(db.or_(Product.name.ilike(pattern), Product.category.ilike(pattern)))
        if search.isdigit():
            order_query = order_query.union(Order.query.filter_by(id=int(search)))
    orders_found = order_query.order_by(Order.created_at.desc()).limit(30).all()
    products_found = product_query.order_by(Product.stock.asc()).limit(20).all()
    selected = None
    if request.args.get("order", "").isdigit():
        selected = Order.query.get(int(request.args["order"]))
    if selected and selected.user_id != current_user.id and not current_user.access:
        if current_user.email.strip().lower() not in current_app.config["ADMIN_EMAILS"]:
            selected = None
    content = render_template_string(ADMIN_TOOLS_HTML, search=search, orders=orders_found, products=products_found, selected_order=selected)
    return render_template_string(ADMIN_SHELL, page_title="Internal tools", active="tools", content=content)


@app.route("/admin/orders/<int:order_id>/status", methods=["POST"])
@admin_required
def admin_order_status(order_id):
    order = Order.query.get_or_404(order_id)
    status = request.form.get("status", "")
    allowed = {"pending", "confirmed", "preparing", "shipped", "delivered", "cancelled"}
    if status not in allowed:
        flash("Choose a valid order status.")
        return redirect(url_for("admin_tools", order=order.id))
    previous = order.status
    order.status = status
    log_admin_action("updated", "Order", order.id, f"Status changed from {previous} to {status}")
    db.session.commit()
    flash("Order status updated.")
    return redirect(url_for("admin_tools", order=order.id))


@app.route("/pricing")
def pricing():
    content = render_template_string(PRICING_HTML, products=Product.query.order_by(Product.price.asc()).all())
    return render_template_string(BASE_HTML, title="Prices and gifting", content=content)


@app.route("/faq")
def faq():
    content = """<section class=\"page-hero small-hero\"><div><p class=\"eyebrow\">A few answers</p><h1>Frequently asked questions</h1><p>Helpful details for your next order.</p></div></section><section class=\"faq-list\"><details><summary>When are sweets prepared?</summary><p>Our products are prepared in small batches so they are ready to enjoy as fresh as possible.</p></details><details><summary>How do I track an order?</summary><p>Sign in and open Orders to see your current order status.</p></details><details><summary>Can I place a bulk order?</summary><p>Yes. Contact the shop with your event date and approximate quantity.</p></details><details><summary>Which payment methods are available?</summary><p>Cash on delivery is currently available. Online payments are not enabled.</p></details></section>"""
    return render_template_string(BASE_HTML, title="Frequently asked questions", content=render_template_string(content))


@app.route("/newsletter", methods=["POST"])
def newsletter_signup():
    email = request.form.get("email", "").strip().lower()
    if len(email) > 120 or "@" not in email or "." not in email.rsplit("@", 1)[-1]:
        flash("Enter a valid email address to join the list.")
    elif NewsletterSubscriber.query.filter_by(email=email).first():
        flash("You’re already on the list. Thank you!")
    else:
        db.session.add(NewsletterSubscriber(email=email))
        db.session.commit()
        flash("You’re on the list. Watch your inbox for a little sweetness.")
    return redirect(url_for("home") + "#newsletter")


@app.errorhandler(404)
def page_not_found(_error):
    return render_template_string(
        ERROR_PAGE_HTML,
        error_code="404",
        error_title="This page took a wrong turn.",
        error_message="The page may have moved, or the link may be a little stale. Let’s get you back to something sweet.",
    ), 404


@app.errorhandler(500)
def internal_server_error(_error):
    db.session.rollback()
    return render_template_string(
        ERROR_PAGE_HTML,
        error_code="500",
        error_title="Something went wrong.",
        error_message="We’re sorry about that. Please try again in a moment or contact customer care if it continues.",
    ), 500


@app.route("/cart/add/<int:product_id>", methods=["POST"])
@login_required
def add_to_cart(product_id):
    product = Product.query.get_or_404(product_id)
    try:
        quantity = int(request.form.get("quantity", 1))
    except (TypeError, ValueError):
        quantity = 1
    if product.stock <= 0 or quantity < 1 or quantity > product.stock:
        flash("That quantity is not available right now.")
        return redirect(url_for("product_detail", product_id=product.id))
    item = CartItem.query.filter_by(user_id=current_user.id, product_id=product.id).first()

    if item:
        if item.quantity + quantity > product.stock:
            flash("There is not enough stock for that quantity.")
            return redirect(url_for("product_detail", product_id=product.id))
        item.quantity += quantity
    else:
        item = CartItem(user_id=current_user.id, product_id=product.id, quantity=quantity)
        db.session.add(item)

    db.session.commit()
    flash(f"{product.name} added to cart.")
    destination = request.form.get("next", "")
    if destination.startswith("/") and not destination.startswith("//"):
        return redirect(destination)
    if request.form.get("next") == "checkout":
        return redirect(url_for("checkout"))
    return redirect(url_for("cart"))


def promo_discount(subtotal):
    if session.get("promo_code") in {"SWEET10", "MITHAI10"}:
        return round(subtotal * 0.10, 2)
    return 0.0


def shipping_cost(method, subtotal):
    if method == "express":
        return 145.0
    return 0.0 if subtotal >= 1200 else 65.0


@app.route("/cart")
@login_required
def cart():
    items = get_cart_items_for_user(current_user.id)
    subtotal = sum(item.product.price * item.quantity for item in items)
    discount = promo_discount(subtotal)
    product_ids = [item.product_id for item in items]
    suggestions = Product.query.filter(Product.id.notin_(product_ids) if product_ids else True).order_by(Product.id.desc()).limit(3).all()
    content = render_template_string(
        CART_HTML,
        cart_items=items,
        subtotal=subtotal,
        discount=discount,
        promo_code=session.get("promo_code"),
        suggestions=suggestions,
        cart_count=sum(item.quantity for item in items),
    )
    return render_template_string(BASE_HTML, title="Basket", content=content)


@app.route("/cart/item/<int:item_id>", methods=["POST"])
@login_required
def update_cart_item(item_id):
    item = CartItem.query.filter_by(id=item_id, user_id=current_user.id).first_or_404()
    if request.form.get("action") == "remove":
        db.session.delete(item)
        flash(f"{item.product.name} removed from your basket.")
    else:
        try:
            quantity = int(request.form.get("quantity", item.quantity))
        except (TypeError, ValueError):
            quantity = item.quantity
        if quantity < 1:
            db.session.delete(item)
        elif quantity > item.product.stock:
            flash("That quantity exceeds current stock.")
            return redirect(url_for("cart"))
        else:
            item.quantity = quantity
    db.session.commit()
    return redirect(url_for("cart"))


@app.route("/cart/promo", methods=["POST"])
@login_required
def apply_promo():
    code = request.form.get("code", "").strip().upper()
    if code in {"SWEET10", "MITHAI10"}:
        session["promo_code"] = code
        flash("Your 10% sweet-shop discount has been applied.")
    else:
        flash("That promo code is not valid. Try SWEET10.")
    return redirect(url_for("cart"))


@app.route("/cart/promo/remove", methods=["POST"])
@login_required
def remove_promo():
    session.pop("promo_code", None)
    flash("Promo code removed.")
    return redirect(url_for("cart"))


@app.route("/wishlist")
@login_required
def wishlist():
    rows = WishlistItem.query.filter_by(user_id=current_user.id).order_by(WishlistItem.created_at.desc()).all()
    content = render_template_string(WISHLIST_HTML, products=[row.product for row in rows])
    return render_template_string(BASE_HTML, title="Saved sweets", content=content)


@app.route("/checkout", methods=["GET", "POST"])
@login_required
def checkout():
    items = get_cart_items_for_user(current_user.id)
    subtotal = sum(item.product.price * item.quantity for item in items)
    discount = promo_discount(subtotal)
    standard_shipping = shipping_cost("standard", subtotal)
    express_shipping = shipping_cost("express", subtotal)

    if not items:
        flash("Your cart is empty.")
        return redirect(url_for("products"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        phone = request.form.get("phone", "").strip()
        address = request.form.get("address", "").strip()
        shipping = request.form.get("shipping", "standard")
        payment = request.form.get("payment", "cash")
        if not name or not email or not address or not phone or len(phone) > 30 or not all(character in "+0123456789() -" for character in phone):
            flash("Add a name, valid email, phone number, and delivery address to continue.")
            return redirect(url_for("checkout"))
        if shipping not in {"standard", "express"} or payment != "cash":
            flash("Choose an available shipping and payment option.")
            return redirect(url_for("checkout"))
        if any(item.quantity > item.product.stock for item in items):
            flash("One or more items no longer have enough stock. Please review your basket.")
            return redirect(url_for("cart"))
        delivery_cost = shipping_cost(shipping, subtotal)
        total = round(subtotal - discount + delivery_cost, 2)
        order = Order(user_id=current_user.id, total=total, status="pending")
        db.session.add(order)
        db.session.flush()
        details = OrderDetails(
            order_id=order.id,
            recipient_name=name,
            email=email,
            phone=phone,
            address=address[:500],
            shipping_method=shipping,
            shipping_cost=delivery_cost,
            subtotal=subtotal,
            discount=discount,
            payment_method=payment,
        )
        db.session.add(details)

        for item in items:
            order_item = OrderItem(
                order_id=order.id,
                product_id=item.product_id,
                quantity=item.quantity,
                price=item.product.price,
            )
            db.session.add(order_item)

            item.product.stock = max(0, item.product.stock - item.quantity)

        for item in items:
            db.session.delete(item)

        db.session.commit()
        session.pop("promo_code", None)
        flash("Order placed successfully.")
        return redirect(url_for("order_confirmation", order_id=order.id))

    previous_details = OrderDetails.query.join(Order).filter(Order.user_id == current_user.id).order_by(Order.id.desc()).first()
    content = render_template_string(
        CHECKOUT_HTML,
        cart_items=items,
        subtotal=subtotal,
        discount=discount,
        promo_code=session.get("promo_code"),
        shipping_standard=standard_shipping,
        shipping_express=express_shipping,
        address=previous_details.address if previous_details else "",
    )
    return render_template_string(BASE_HTML, title="Checkout", content=content)


@app.route("/orders/<int:order_id>/confirmation")
@login_required
def order_confirmation(order_id):
    order = Order.query.filter_by(id=order_id, user_id=current_user.id).first_or_404()
    details = OrderDetails.query.filter_by(order_id=order.id).first_or_404()
    delivery_days = 2 if details.shipping_method == "express" else 4
    content = render_template_string(
        ORDER_CONFIRMATION_HTML,
        order=order,
        order_details=details,
        estimated_delivery=(order.created_at or datetime.utcnow()) + timedelta(days=delivery_days),
    )
    return render_template_string(BASE_HTML, title="Order confirmed", content=content)


@app.route("/orders/<int:order_id>/receipt.csv")
@login_required
def download_receipt(order_id):
    order = Order.query.filter_by(id=order_id, user_id=current_user.id).first_or_404()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Order", order.id])
    writer.writerow(["Date", order.created_at.isoformat() if order.created_at else ""])
    writer.writerow(["Product", "Quantity", "Unit price", "Line total"])
    for item in order.items:
        writer.writerow([item.product.name, item.quantity, f"{item.price:.2f}", f"{item.price * item.quantity:.2f}"])
    writer.writerow(["Total", "", "", f"{order.total:.2f}"])
    return Response(output.getvalue(), mimetype="text/csv", headers={"Content-Disposition": f"attachment; filename=order-{order.id}.csv"})


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"].strip()
        email = request.form["email"].strip()
        password = request.form["password"]

        if len(password) < 8:
            flash("Use a password with at least 8 characters.")
            return redirect(url_for("register"))

        if User.query.filter((User.username == username) | (User.email == email)).first():
            flash("User already exists. Please choose another username or email.")
            return redirect(url_for("register"))

        user = User(username=username, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        login_user(user)
        flash("Registration successful.")
        return redirect(url_for("onboarding"))

    form = render_template_string(AUTH_FORM_HTML, mode="signup")
    return render_template_string(AUTH_SHELL, title="Create account", content=form)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]
        user = User.query.filter((User.username == username) | (User.email == username)).first()

        if user and user.check_password(password):
            login_user(user, remember=bool(request.form.get("remember")))
            flash("Login successful.")
            return redirect(url_for("dashboard"))

        flash("Invalid username or password.")
        return redirect(url_for("login"))

    form = render_template_string(AUTH_FORM_HTML, mode="login")
    return render_template_string(AUTH_SHELL, title="Sign in", content=form)


@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    content = """
    <main class="auth-help-page"><a class="brand" href="{{ url_for('home') }}"><span class="brand-mark">J</span><span>Jai Hanuman<br><small>Sweets</small></span></a>
    <section class="auth-form-card"><p class="eyebrow">Account support</p><h1>Need help signing in?</h1><p>We are not yet sending automated password reset emails. Contact our team and we will help you regain access.</p><a class="btn btn-primary full-width" href="mailto:hello@jaihanumansweets.in?subject=Account%20access%20help">Email customer care</a><a class="auth-back-link" href="{{ url_for('login') }}">Back to sign in</a></section></main>
    """
    return render_template_string(AUTH_SHELL, title="Account help", content=render_template_string(content))


@app.route("/terms")
def terms():
    return render_template_string(AUTH_SHELL, title="Terms and privacy", content=render_template_string(TERMS_HTML))


@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Logged out.")
    return redirect(url_for("home"))


with app.app_context():
    db.create_all()

    if Product.query.count() == 0:
        products = [
            Product(name="Chocolate Truffle", description="Rich chocolate centers with a smooth ganache finish.", price=12.5, stock=20, category="Cakes", image="https://images.unsplash.com/photo-1551024601-bec78aea704b?auto=format&fit=crop&w=800&q=80"),
            Product(name="Strawberry Cheesecake", description="Creamy cheesecake with a fresh strawberry topping.", price=15.0, stock=15, category="Desserts", image="https://images.unsplash.com/photo-1533134242443-d4fd215305ad?auto=format&fit=crop&w=800&q=80"),
            Product(name="Mango Kulfi", description="Traditional Indian frozen dessert with tropical mango flavor.", price=9.5, stock=25, category="Ice Cream", image="https://images.unsplash.com/photo-1570197788417-0e823ef4b963?auto=format&fit=crop&w=800&q=80"),
            Product(name="Saffron Laddu", description="Soft golden laddus with saffron and nuts.", price=11.0, stock=30, category="Sweets", image="https://images.unsplash.com/photo-1606313564200-e75d5e30476c?auto=format&fit=crop&w=800&q=80"),
            Product(name="Vanilla Cupcake", description="Light vanilla sponge topped with whipped cream.", price=6.5, stock=40, category="Bakery", image="https://images.unsplash.com/photo-1486427944299-d1955d23e34d?auto=format&fit=crop&w=800&q=80"),
        ]
        db.session.add_all(products)
        db.session.commit()


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
