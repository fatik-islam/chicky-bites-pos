from flask import Flask, render_template, redirect, url_for, session, request, flash
from models import db, User, Category, Product, Order, OrderItem
from forms import LoginForm, CategoryForm, ProductForm
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from sqlalchemy.sql import func

app = Flask(__name__)
app.secret_key = 'SOME_RANDOM_SECRET_KEY'  # Change this to something secure

# Configure the database
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///chicky_bites.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

# Uncomment & run once to create tables:
# with app.app_context():
#     db.create_all()

# --------------------------------------------------
# Authentication & Login
# --------------------------------------------------
@app.route('/', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    form = LoginForm()
    if form.validate_on_submit():
        username = form.username.data
        password = form.password.data
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid credentials', 'danger')
    return render_template('login.html', form=form)

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('login'))

def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# --------------------------------------------------
# Dashboard
# --------------------------------------------------
@app.route('/dashboard')
@login_required
def dashboard():
    # Example: total orders, total revenue, and recent orders
    total_orders = db.session.query(func.count(Order.id)).scalar() or 0
    total_revenue = db.session.query(func.sum(Order.total_amount)).scalar() or 0.0
    recent_orders = (
        db.session.query(Order)
        .order_by(Order.date_ordered.desc())
        .limit(5)
        .all()
    )

    return render_template(
        'dashboard.html',
        total_orders=total_orders,
        total_revenue=total_revenue,
        recent_orders=recent_orders
    )

# --------------------------------------------------
# Categories
# --------------------------------------------------
@app.route('/categories', methods=['GET', 'POST'])
@login_required
def categories():
    form = CategoryForm()
    if form.validate_on_submit():
        new_cat = Category(name=form.name.data)
        db.session.add(new_cat)
        db.session.commit()
        flash('Category added successfully!', 'success')
        return redirect(url_for('categories'))
    
    all_categories = Category.query.all()
    return render_template('categories.html', form=form, categories=all_categories)

# --------------------------------------------------
# Products
# --------------------------------------------------
@app.route('/products', methods=['GET', 'POST'])
@login_required
def products():
    form = ProductForm()
    # Populate category choices
    form.category_id.choices = [(c.id, c.name) for c in Category.query.all()]

    if form.validate_on_submit():
        new_product = Product(
            name=form.name.data,
            price=form.price.data,
            stock=form.stock.data,
            category_id=form.category_id.data
        )
        db.session.add(new_product)
        db.session.commit()
        flash('Product added successfully!', 'success')
        return redirect(url_for('products'))
    
    all_products = Product.query.all()
    return render_template('products.html', form=form, products=all_products)

@app.route('/update_stock/<int:product_id>', methods=['POST'])
@login_required
def update_stock(product_id):
    product = Product.query.get_or_404(product_id)
    new_stock = request.form.get('stock', type=int)
    product.stock = new_stock
    db.session.commit()
    flash('Stock updated!', 'success')
    return redirect(url_for('products'))

# --------------------------------------------------
# Orders (POS)
# --------------------------------------------------
@app.route('/orders', methods=['GET', 'POST'])
@login_required
def orders():
    """
    Displays categories and products as clickable buttons,
    a cart table, search box, etc. 
    """
    categories = Category.query.all()
    products = Product.query.all()

    # If you plan to handle POST to save the order in DB, you can do so here.
    if request.method == 'POST':
        # Example pseudo-code for saving orders if needed:
        # cart_data = request.json.get('cart')
        # create an Order and its OrderItems
        pass

    return render_template('orders.html', products=products, categories=categories)

@app.route('/print_order/<int:order_id>')
@login_required
def print_order(order_id):
    order = Order.query.get_or_404(order_id)
    return render_template('print_order.html', order=order)

# --------------------------------------------------
# Sales Report
# --------------------------------------------------
@app.route('/sales_report')
@login_required
def sales_report():
    daily_sales = db.session.query(
        func.date(Order.date_ordered).label('date'),
        func.sum(Order.total_amount).label('daily_total')
    ).group_by(func.date(Order.date_ordered)).all()

    return render_template('sales_report.html', daily_sales=daily_sales)


if __name__ == '__main__':
    app.run(debug=True)

