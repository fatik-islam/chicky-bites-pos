# app.py

import time
import os
from dotenv import load_dotenv
from flask import (
    Flask, render_template, redirect, url_for, request,
    flash, jsonify, make_response, abort, session
)
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager, login_user, logout_user,
    login_required, current_user
)
from werkzeug.security import generate_password_hash, check_password_hash
from forms import (
    LoginForm, RegistrationForm,
    CategoryForm, TableForm, MainProductForm, SubProductForm,
    OrderForm, SalesReportForm,
    ChangePasswordForm, StartSessionForm, EndSessionForm
)
from models import db, User, Category, Table, Product, Order, OrderItem, SessionLog, ProductComponent, OrderType
from datetime import datetime, timedelta
from sqlalchemy.sql import func
import csv
from io import StringIO
from fpdf import FPDF
from functools import wraps
from flask_wtf.csrf import CSRFProtect, generate_csrf
import json

# ----------------------------------------------------------------------------
# Load environment variables from .env file
# ----------------------------------------------------------------------------
load_dotenv()

# ----------------------------------------------------------------------------
# Initialize Flask app
# ----------------------------------------------------------------------------
app = Flask(__name__)

# ----------------------------------------------------------------------------
# Configuration using environment variables
# ----------------------------------------------------------------------------
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'YOUR_SECURE_SECRET_KEY')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('SQLALCHEMY_DATABASE_URI', 'sqlite:///chicky_bites.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Optional: You can read DEBUG from env if desired
# app.debug = os.getenv('DEBUG', 'False').lower() == 'true'

# ----------------------------------------------------------------------------
# Initialize Extensions
# ----------------------------------------------------------------------------
db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'warning'
csrf = CSRFProtect(app)

# --------------------------------------------------
# Context Processor for CSRF Token
# --------------------------------------------------
@app.context_processor
def inject_csrf_token():
    return dict(csrf_token=lambda: generate_csrf())

# --------------------------------------------------
# Decorators for RBAC
# --------------------------------------------------
def roles_required(*roles):
    """
    Decorator to restrict access to users with specified roles.
    Usage: @roles_required('admin', 'cashier')
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return login_manager.unauthorized()
            if current_user.role not in roles:
                abort(403)
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# --------------------------------------------------
# User Loader for Flask-Login
# --------------------------------------------------
@login_manager.user_loader
def load_user(user_id):
    try:
        return User.query.get(int(user_id))
    except (ValueError, TypeError):
        return None

# --------------------------------------------------
# Session Handling
# --------------------------------------------------
def start_user_session():
    """
    Clears any existing session data, then starts a new session from zero.
    Uses time.time() for a numeric Unix timestamp, which aligns well with JS Date.now().
    """
    end_user_session()  # Force-clear old data if it wasn't ended properly

    session['session_active'] = True
    session['session_start_timestamp'] = time.time()  # Numeric epoch in seconds
    session['session_orders'] = 0
    session['session_revenue'] = 0.0

    new_log = SessionLog(
        user_id=current_user.id,
        start_time=datetime.utcnow(),
        total_orders=0,
        total_revenue=0.0
    )
    db.session.add(new_log)
    db.session.commit()
    session['session_log_id'] = new_log.id

def end_user_session():
    """
    Ends the current session, updates the DB SessionLog record if it exists,
    then clears ephemeral session data so everything resets to zero.
    """
    if session.get('session_active'):
        log_id = session.get('session_log_id')
        if log_id:
            log = SessionLog.query.get(log_id)
            if log:
                log.end_time = datetime.utcnow()
                log.total_orders = session.get('session_orders', 0)
                log.total_revenue = session.get('session_revenue', 0.0)
                db.session.commit()

    session.pop('session_active', None)
    session.pop('session_start_timestamp', None)
    session.pop('session_orders', None)
    session.pop('session_revenue', None)
    session.pop('session_log_id', None)

# --------------------------------------------------
# Routes for Session
# --------------------------------------------------
@app.route('/start_session', methods=['POST'])
@login_required
@roles_required('admin', 'cashier')
def start_session():
    form = StartSessionForm()
    if form.validate_on_submit():
        if session.get('session_active'):
            flash('Session is already active.', 'warning')
        else:
            start_user_session()
            flash('Session Started Successfully!', 'success')
    else:
        flash('Invalid form submission.', 'danger')
    return redirect(url_for('dashboard'))  # Redirect to common dashboard

@app.route('/end_session', methods=['POST'])
@login_required
@roles_required('admin', 'cashier')
def end_session():
    form = EndSessionForm()
    if form.validate_on_submit():
        # Check for any pending orders
        pending_orders_count = Order.query.filter_by(status='Pending').count()
        if pending_orders_count > 0:
            flash('Cannot end session while there are pending bills. Please resolve all pending orders before ending the session.', 'danger')
            return redirect(url_for('dashboard'))  # Redirect to common dashboard

        if not session.get('session_active'):
            flash('No active session to end.', 'warning')
        else:
            end_user_session()
            flash('Session ended.', 'info')
    else:
        flash('Invalid form submission.', 'danger')
    return redirect(url_for('dashboard'))  # Redirect to common dashboard

# --------------------------------------------------
# Root Route
# --------------------------------------------------
@app.route('/', methods=['GET'])
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    else:
        return redirect(url_for('login'))

# --------------------------------------------------
# Main Routes
# --------------------------------------------------
@app.route('/register', methods=['GET', 'POST'])
@login_required
@roles_required('admin')
def register():
    form = RegistrationForm(prefix='register')
    change_form = ChangePasswordForm(prefix='change')
    if request.method == 'POST':
        if 'register-submit' in request.form and form.validate_on_submit():
            try:
                hashed_password = generate_password_hash(form.password.data)
                new_user = User(
                    username=form.username.data,
                    password=hashed_password,
                    role=form.role.data
                )
                db.session.add(new_user)
                db.session.commit()
                flash(f'User {new_user.username} registered successfully as {new_user.role}!', 'success')
                return redirect(url_for('admin_dashboard'))
            except Exception as e:
                db.session.rollback()
                flash(f'Error registering user: {e}', 'danger')
        elif 'change-submit' in request.form and change_form.validate_on_submit():
            if not check_password_hash(current_user.password, change_form.current_password.data):
                flash('Current password is incorrect.', 'danger')
                return redirect(url_for('register'))
            try:
                current_user.password = generate_password_hash(change_form.new_password.data)
                db.session.commit()
                flash('Your password has been updated!', 'success')
                return redirect(url_for('dashboard'))
            except Exception as e:
                db.session.rollback()
                flash(f'Error updating password: {e}', 'danger')
    return render_template('register.html', form=form, change_form=change_form)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    form = LoginForm()
    if form.validate_on_submit():
        try:
            user = User.query.filter_by(username=form.username.data).first()
            if user and check_password_hash(user.password, form.password.data):
                login_user(user)
                flash('Logged in successfully.', 'success')
                next_page = request.args.get('next')
                return redirect(next_page) if next_page else redirect(url_for('dashboard'))
            else:
                flash('Invalid username or password.', 'danger')
        except Exception as e:
            flash(f'Error during login: {e}', 'danger')
    return render_template('login.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

# --------------------------------------------------
# Dashboard Route
# --------------------------------------------------
@app.route('/dashboard')
@login_required
def dashboard():
    try:
        session_active = session.get('session_active', False)
        session_orders = session.get('session_orders', 0)
        session_revenue = session.get('session_revenue', 0.0)
        session_start_timestamp = session.get('session_start_timestamp', 0.0)

        if session_active and session_start_timestamp > 0:
            start_time = datetime.fromtimestamp(session_start_timestamp)

            dine_in_orders = Order.query.filter(
                Order.order_types.any(OrderType.name == 'Dine-in'),
                Order.date_ordered >= start_time
            ).count()
            takeaway_orders = Order.query.filter(
                Order.order_types.any(OrderType.name == 'Takeaway'),
                Order.date_ordered >= start_time
            ).count()
            delivery_orders = Order.query.filter(
                Order.order_types.any(OrderType.name == 'Delivery'),
                Order.date_ordered >= start_time
            ).count()

            dine_in_revenue = db.session.query(func.sum(Order.total_amount)).filter(
                Order.order_types.any(OrderType.name == 'Dine-in'),
                Order.date_ordered >= start_time
            ).scalar() or 0.0
            takeaway_revenue = db.session.query(func.sum(Order.total_amount)).filter(
                Order.order_types.any(OrderType.name == 'Takeaway'),
                Order.date_ordered >= start_time
            ).scalar() or 0.0
            delivery_revenue = db.session.query(func.sum(Order.total_amount)).filter(
                Order.order_types.any(OrderType.name == 'Delivery'),
                Order.date_ordered >= start_time
            ).scalar() or 0.0

            recent_orders = Order.query.filter(
                Order.date_ordered >= start_time
            ).order_by(Order.date_ordered.desc()).limit(10).all()

            sales_trends_query = db.session.query(
                func.date(Order.date_ordered).label('date'),
                func.sum(Order.total_amount).label('total_sales')
            ).filter(
                Order.date_ordered >= start_time
            ).group_by(
                func.date(Order.date_ordered)
            ).order_by(
                func.date(Order.date_ordered)
            )
            sales_trends = sales_trends_query.all()
        else:
            dine_in_orders = takeaway_orders = delivery_orders = 0
            dine_in_revenue = takeaway_revenue = delivery_revenue = 0.0
            recent_orders = []
            sales_trends = []

        pending_orders = Order.query.filter_by(status='Pending').count()

    except Exception as e:
        flash(f'Error fetching dashboard data: {e}', 'danger')
        session_active = False
        session_orders = 0
        session_revenue = 0.0
        session_start_timestamp = 0.0
        dine_in_orders = takeaway_orders = delivery_orders = 0
        dine_in_revenue = takeaway_revenue = delivery_revenue = 0.0
        recent_orders = []
        sales_trends = []
        pending_orders = 0

    start_session_form = StartSessionForm()
    end_session_form = EndSessionForm()

    return render_template(
        'dashboard.html',
        session_active=session_active,
        session_orders=session_orders,
        session_revenue=session_revenue,
        session_start_timestamp=session_start_timestamp,
        dine_in_orders=dine_in_orders,
        takeaway_orders=takeaway_orders,
        delivery_orders=delivery_orders,
        dine_in_revenue=dine_in_revenue,
        takeaway_revenue=takeaway_revenue,
        delivery_revenue=delivery_revenue,
        recent_orders=recent_orders,
        pending_orders=pending_orders,
        sales_trends=sales_trends,
        start_session_form=start_session_form,
        end_session_form=end_session_form
    )

# --------------------------------------------------
# Admin Dashboard Route
# --------------------------------------------------
@app.route('/admin_dashboard', methods=['GET', 'POST'])
@login_required
@roles_required('admin')
def admin_dashboard():
    try:
        start_date = request.args.get('start_date', default=None, type=str)
        end_date = request.args.get('end_date', default=None, type=str)
        order_type = request.args.get('order_type', default='All', type=str)

        if start_date:
            try:
                start_date_obj = datetime.strptime(start_date, '%Y-%m-%d')
            except ValueError:
                flash('Invalid start date format. Use YYYY-MM-DD.', 'danger')
                start_date_obj = None
        else:
            start_date_obj = None

        if end_date:
            try:
                end_date_obj = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1) - timedelta(seconds=1)
            except ValueError:
                flash('Invalid end date format. Use YYYY-MM-DD.', 'danger')
                end_date_obj = None
        else:
            end_date_obj = None

        order_query = Order.query

        if start_date_obj:
            order_query = order_query.filter(Order.date_ordered >= start_date_obj)
        if end_date_obj:
            order_query = order_query.filter(Order.date_ordered <= end_date_obj)
        if order_type != 'All':
            order_query = order_query.filter(Order.order_types.any(OrderType.name == order_type))

        dine_in_orders = Order.query.filter(
            Order.order_types.any(OrderType.name == 'Dine-in'),
            Order.date_ordered >= start_date_obj if start_date_obj else True,
            Order.date_ordered <= end_date_obj if end_date_obj else True
        ).count()

        takeaway_orders = Order.query.filter(
            Order.order_types.any(OrderType.name == 'Takeaway'),
            Order.date_ordered >= start_date_obj if start_date_obj else True,
            Order.date_ordered <= end_date_obj if end_date_obj else True
        ).count()

        delivery_orders = Order.query.filter(
            Order.order_types.any(OrderType.name == 'Delivery'),
            Order.date_ordered >= start_date_obj if start_date_obj else True,
            Order.date_ordered <= end_date_obj if end_date_obj else True
        ).count()

        dine_in_revenue = db.session.query(func.sum(Order.total_amount)).filter(
            Order.order_types.any(OrderType.name == 'Dine-in'),
            Order.date_ordered >= start_date_obj if start_date_obj else True,
            Order.date_ordered <= end_date_obj if end_date_obj else True
        ).scalar() or 0.0
        takeaway_revenue = db.session.query(func.sum(Order.total_amount)).filter(
            Order.order_types.any(OrderType.name == 'Takeaway'),
            Order.date_ordered >= start_date_obj if start_date_obj else True,
            Order.date_ordered <= end_date_obj if end_date_obj else True
        ).scalar() or 0.0
        delivery_revenue = db.session.query(func.sum(Order.total_amount)).filter(
            Order.order_types.any(OrderType.name == 'Delivery'),
            Order.date_ordered >= start_date_obj if start_date_obj else True,
            Order.date_ordered <= end_date_obj if end_date_obj else True
        ).scalar() or 0.0

        recent_orders = order_query.order_by(Order.date_ordered.desc()).limit(10).all()

        sales_trends_query = db.session.query(
            func.date(Order.date_ordered).label('date'),
            func.sum(Order.total_amount).label('total_sales')
        ).filter(
            Order.date_ordered >= start_date_obj if start_date_obj else True,
            Order.date_ordered <= end_date_obj if end_date_obj else True,
            Order.order_types.any(OrderType.name == order_type) if order_type != 'All' else True
        ).group_by(
            func.date(Order.date_ordered)
        ).order_by(
            func.date(Order.date_ordered)
        )
        sales_trends = sales_trends_query.all()
    except Exception as e:
        flash(f'Error fetching admin dashboard data: {e}', 'danger')
        dine_in_orders = takeaway_orders = delivery_orders = 0
        dine_in_revenue = takeaway_revenue = delivery_revenue = 0.0
        recent_orders = []
        sales_trends = []

    return render_template(
        'admin_dashboard.html',
        dine_in_orders=dine_in_orders,
        takeaway_orders=takeaway_orders,
        delivery_orders=delivery_orders,
        dine_in_revenue=dine_in_revenue,
        takeaway_revenue=takeaway_revenue,
        delivery_revenue=delivery_revenue,
        recent_orders=recent_orders,
        start_date=start_date,
        end_date=end_date,
        order_type=order_type,
        sales_trends=sales_trends
    )

# --------------------------------------------------
# Categories Route
# --------------------------------------------------
@app.route('/categories', methods=['GET', 'POST'])
@login_required
@roles_required('admin')
def categories():
    form_category = CategoryForm()
    form_table = TableForm()
    if request.method == 'POST':
        if 'add_category' in request.form and form_category.validate_on_submit():
            try:
                new_cat = Category(name=form_category.name.data)
                db.session.add(new_cat)
                db.session.commit()
                flash('Category added successfully!', 'success')
                return redirect(url_for('categories'))
            except Exception as e:
                db.session.rollback()
                flash(f'Error adding category: {e}', 'danger')
        elif 'add_table' in request.form and form_table.validate_on_submit():
            try:
                new_table = Table(table_number=form_table.table_number.data)
                db.session.add(new_table)
                db.session.commit()
                flash('Table number added successfully!', 'success')
                return redirect(url_for('categories'))
            except Exception as e:
                db.session.rollback()
                flash(f'Error adding table number: {e}', 'danger')

    all_categories = Category.query.order_by(Category.name).all()
    all_tables = Table.query.order_by(Table.table_number).all()
    return render_template('categories.html',
                           form_category=form_category,
                           form_table=form_table,
                           categories=all_categories,
                           tables=all_tables)

@app.route('/delete_category/<int:category_id>', methods=['POST'])
@login_required
@roles_required('admin')
def delete_category(category_id):
    form = CategoryForm()
    if form.validate_on_submit():
        try:
            category = Category.query.get_or_404(category_id)
            if category.products:
                flash('Cannot delete category with associated products. Please delete or reassign its products first.', 'danger')
                return redirect(url_for('categories'))
            db.session.delete(category)
            db.session.commit()
            flash('Category deleted successfully!', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error deleting category: {e}', 'danger')
    else:
        flash('Invalid form submission.', 'danger')
    return redirect(url_for('categories'))

@app.route('/edit_category/<int:category_id>', methods=['POST'])
@login_required
@roles_required('admin')
def edit_category(category_id):
    form = CategoryForm()
    if form.validate_on_submit():
        try:
            category = Category.query.get_or_404(category_id)
            category.name = form.name.data
            db.session.commit()
            flash('Category updated successfully!', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating category: {e}', 'danger')
    else:
        flash('Invalid data submitted.', 'danger')
    return redirect(url_for('categories'))

@app.route('/delete_table/<int:table_id>', methods=['POST'])
@login_required
@roles_required('admin')
def delete_table(table_id):
    form = TableForm()
    if form.validate_on_submit():
        try:
            table = Table.query.get_or_404(table_id)
            if table.orders:
                flash('Cannot delete table with associated orders. Please reassign or complete its orders first.', 'danger')
                return redirect(url_for('categories'))
            db.session.delete(table)
            db.session.commit()
            flash('Table number deleted successfully!', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error deleting table number: {e}', 'danger')
    else:
        flash('Invalid form submission.', 'danger')
    return redirect(url_for('categories'))

@app.route('/edit_table/<int:table_id>', methods=['POST'])
@login_required
@roles_required('admin')
def edit_table(table_id):
    form = TableForm()
    if form.validate_on_submit():
        try:
            table = Table.query.get_or_404(table_id)
            table.table_number = form.table_number.data
            db.session.commit()
            flash('Table number updated successfully!', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating table number: {e}', 'danger')
    else:
        flash('Invalid data submitted.', 'danger')
    return redirect(url_for('categories'))

# --------------------------------------------------
# Products Route
# --------------------------------------------------
@app.route('/products', methods=['GET', 'POST'])
@login_required
@roles_required('admin')
def products():
    form_main = MainProductForm(prefix='main')
    form_sub = SubProductForm(prefix='sub')

    sub_product_choices = [(0, 'Select Sub-Product')] + [
        (p.id, p.name)
        for p in Product.query.filter_by(is_sub_product=True).order_by(Product.name).all()
    ]

    form_main.components.entries = []
    for _ in range(1):
        form_main.components.append_entry()

    all_products = Product.query.order_by(Product.name).all()

    if request.method == 'POST':
        if 'add_main_product' in request.form and form_main.validate_on_submit():
            try:
                new_product = Product(
                    name=form_main.name.data,
                    price=form_main.price.data,
                    stock=0,
                    category_id=form_main.category_id.data,
                    is_sub_product=False
                )
                db.session.add(new_product)
                db.session.commit()

                for component_form in form_main.components.entries:
                    sub_id = component_form.form.sub_product_id.data
                    qty = component_form.form.quantity.data
                    if sub_id == 0 or qty < 1:
                        continue
                    sub_product = Product.query.get(sub_id)
                    if sub_product and sub_product.is_sub_product:
                        # Prevent circular dependencies
                        circular_assoc = ProductComponent.query.filter_by(
                            product_id=sub_product.id,
                            sub_product_id=new_product.id
                        ).first()
                        if circular_assoc:
                            flash(f"Circular dependency detected between {new_product.name} and {sub_product.name}.", "danger")
                            continue
                        existing_assoc = ProductComponent.query.filter_by(
                            product_id=new_product.id,
                            sub_product_id=sub_product.id
                        ).first()
                        if existing_assoc:
                            existing_assoc.quantity = qty
                        else:
                            component = ProductComponent(
                                product_id=new_product.id,
                                sub_product_id=sub_product.id,
                                quantity=qty
                            )
                            db.session.add(component)
                db.session.commit()
                flash('Main product added successfully!', 'success')
                return redirect(url_for('products'))
            except Exception as e:
                db.session.rollback()
                flash(f'Error adding main product: {e}', 'danger')

        elif 'add_sub_product' in request.form and form_sub.validate_on_submit():
            try:
                new_sub_product = Product(
                    name=form_sub.name.data,
                    price=0.0,
                    stock=form_sub.stock.data,
                    category_id=None,
                    is_sub_product=True
                )
                db.session.add(new_sub_product)
                db.session.commit()
                flash('Sub-product added successfully!', 'success')
                return redirect(url_for('products'))
            except Exception as e:
                db.session.rollback()
                flash(f'Error adding sub-product: {e}', 'danger')

    return render_template(
        'products.html',
        products=all_products,
        sub_product_choices=sub_product_choices,
        form_main=form_main,
        form_sub=form_sub
    )

@app.route('/edit_product/<int:product_id>', methods=['POST'])
@login_required
@roles_required('admin')
def edit_product(product_id):
    product = Product.query.get_or_404(product_id)

    if product.is_sub_product:
        form = SubProductForm(prefix=f'sub-{product_id}')
        if form.validate_on_submit():
            try:
                product.name = form.name.data
                product.stock = form.stock.data
                db.session.commit()
                flash('Sub-product updated successfully!', 'success')
            except Exception as e:
                db.session.rollback()
                flash(f'Error updating sub-product: {e}', 'danger')
        else:
            flash('Invalid data submitted for editing sub-product.', 'danger')
    else:
        form = MainProductForm(prefix=f'main-{product_id}')
        if form.validate_on_submit():
            try:
                product.name = form.name.data
                product.price = form.price.data
                product.category_id = form.category_id.data
                db.session.commit()

                # Delete existing components
                ProductComponent.query.filter_by(product_id=product.id).delete()

                # Add new components
                for component_form in form.components.entries:
                    sub_id = component_form.form.sub_product_id.data
                    qty = component_form.form.quantity.data
                    if sub_id == 0 or qty < 1:
                        continue
                    sub_product = Product.query.get(sub_id)
                    if sub_product and sub_product.is_sub_product:
                        # Prevent circular dependencies
                        circular_assoc = ProductComponent.query.filter_by(
                            product_id=sub_product.id,
                            sub_product_id=product.id
                        ).first()
                        if circular_assoc:
                            flash(f"Circular dependency detected between {product.name} and {sub_product.name}.", "danger")
                            continue
                        existing_assoc = ProductComponent.query.filter_by(
                            product_id=product.id,
                            sub_product_id=sub_product.id
                        ).first()
                        if existing_assoc:
                            existing_assoc.quantity = qty
                        else:
                            component = ProductComponent(
                                product_id=product.id,
                                sub_product_id=sub_product.id,
                                quantity=qty
                            )
                            db.session.add(component)
                db.session.commit()
                flash('Main product updated successfully!', 'success')
            except Exception as e:
                db.session.rollback()
                flash(f'Error updating main product: {e}', 'danger')
        else:
            flash('Invalid data submitted for editing main product.', 'danger')
    return redirect(url_for('products'))

@app.route('/delete_product/<int:product_id>', methods=['POST'])
@login_required
@roles_required('admin')
def delete_product(product_id):
    form = MainProductForm()
    if form.validate_on_submit():
        try:
            product = Product.query.get_or_404(product_id)
            associated_order_items = OrderItem.query.filter_by(product_id=product.id).first()
            associated_as_component = ProductComponent.query.filter(
                (ProductComponent.sub_product_id == product.id) |
                (ProductComponent.product_id == product.id)
            ).first()
            if associated_order_items or associated_as_component:
                flash('Cannot delete product associated with orders or other products.', 'danger')
                return redirect(url_for('products'))
            db.session.delete(product)
            db.session.commit()
            flash('Product deleted successfully!', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error deleting product: {e}', 'danger')
    else:
        flash('Invalid form submission.', 'danger')
    return redirect(url_for('products'))

@app.route('/get_product_components', methods=['GET'])
@login_required
@roles_required('admin')
def get_product_components():
    product_id = request.args.get('product_id', type=str)
    if not product_id:
        return jsonify({'error': 'Invalid product ID.'}), 400

    try:
        product_id = int(product_id)
    except ValueError:
        return jsonify({'error': 'Product ID must be an integer.'}), 400

    main_product = Product.query.get(product_id)
    if not main_product:
        return jsonify({'error': 'Product not found.'}), 404

    if main_product.is_sub_product:
        return jsonify({'error': 'Sub-products do not have components.'}), 400

    components = []
    for assoc in main_product.component_associations:
        components.append({
            'sub_product_id': assoc.sub_product_id,
            'quantity': assoc.quantity,
            'sub_product_name': assoc.sub_product.name
        })

    return jsonify({'components': components})

# --------------------------------------------------
# Orders Route
# --------------------------------------------------
@app.route('/orders', methods=['GET', 'POST'])
@login_required
@roles_required('admin', 'cashier')
def orders():
    if not session.get('session_active'):
        flash('No active session. Please start a session to place orders.', 'warning')
        return redirect(url_for('dashboard'))

    form = OrderForm()
    categories = Category.query.order_by(Category.name).all()
    products = Product.query.order_by(Product.name).all()
    pending_orders = Order.query.filter_by(status='Pending').order_by(Order.date_ordered.desc()).all()

    if request.method == 'POST':
        order_id = request.form.get('order_id')
        if order_id:
            order = Order.query.get(order_id)
            if not order:
                flash('Order not found.', 'danger')
                return redirect(url_for('orders'))
            if order.status != 'Pending':
                flash('Only pending orders can be edited.', 'warning')
                return redirect(url_for('orders'))

        if 'save_order' in request.form:
            action = 'save_order'
        elif 'print_kitchen' in request.form:
            action = 'print_kitchen'
        else:
            action = 'unknown'

        if form.validate_on_submit():
            try:
                selected_order_types = form.order_type.data
                table_id = form.table_id.data if 'Dine-in' in selected_order_types else None
                address = form.address.data if 'Delivery' in selected_order_types else None
                contact_number = form.contact_number.data if ('Delivery' in selected_order_types or
                                                              'Takeaway' in selected_order_types) else None
                first_name = form.first_name.data if 'Delivery' in selected_order_types else None
                last_name = form.last_name.data if 'Delivery' in selected_order_types else None

                cart_json = form.cart.data or '[]'
                try:
                    cart = json.loads(cart_json)
                except json.JSONDecodeError:
                    cart = []

                if not cart:
                    flash('Cart cannot be empty.', 'danger')
                    return redirect(url_for('orders'))

                total_amount = 0.0
                processed_cart = []
                for item in cart:
                    product_id = item.get('id')
                    quantity = item.get('quantity', 1)
                    product = Product.query.get(product_id)
                    if not product:
                        flash(f'Product with ID {product_id} does not exist.', 'warning')
                        continue

                    try:
                        quantity = int(quantity)
                        if quantity < 1:
                            flash(f'Invalid quantity for product {product.name}.', 'warning')
                            continue
                    except ValueError:
                        flash(f'Invalid quantity for product {product.name}.', 'warning')
                        continue

                    if product.is_sub_product:
                        if product.stock < quantity:
                            flash(f'Insufficient stock for product {product.name}. Available: {product.stock}', 'warning')
                            continue
                        total_amount += product.price * quantity
                        processed_cart.append({
                            'id': product.id,
                            'name': product.name,
                            'price': product.price,
                            'quantity': quantity
                        })
                    else:
                        associations = ProductComponent.query.filter_by(product_id=product.id).all()
                        if not associations:
                            flash(f'Main product {product.name} has no associated sub-products.', 'warning')
                            continue
                        insufficient_stock = False
                        for assoc in associations:
                            sub_product = assoc.sub_product
                            required_qty = assoc.quantity * quantity
                            if sub_product.stock < required_qty:
                                flash(f'Insufficient stock for sub-product {sub_product.name}. '
                                      f'Required: {required_qty}, Available: {sub_product.stock}', 'warning')
                                insufficient_stock = True
                        if insufficient_stock:
                            continue
                        for assoc in associations:
                            sub_product = assoc.sub_product
                            required_qty = assoc.quantity * quantity
                            sub_product.stock -= required_qty
                            total_amount += sub_product.price * required_qty
                            processed_cart.append({
                                'id': sub_product.id,
                                'name': sub_product.name,
                                'price': sub_product.price,
                                'quantity': required_qty
                            })

                if not processed_cart:
                    flash('No valid items in cart to process.', 'danger')
                    return redirect(url_for('orders'))

                # If editing an existing order
                if order_id:
                    order.order_types = []
                    for ot_name in selected_order_types:
                        ot = OrderType.query.filter_by(name=ot_name).first()
                        if ot:
                            order.order_types.append(ot)

                    order.table_id = table_id
                    order.address = address
                    order.contact_number = contact_number
                    order.first_name = first_name
                    order.last_name = last_name
                    order.total_amount = total_amount

                    # Return stock from old items
                    for existing_item in order.order_items:
                        existing_product = Product.query.get(existing_item.product_id)
                        if existing_product and existing_product.is_sub_product:
                            existing_product.stock += existing_item.quantity
                        db.session.delete(existing_item)

                    db.session.commit()

                    # Add new items
                    for item in processed_cart:
                        order_item = OrderItem(
                            order_id=order.id,
                            product_id=item['id'],
                            quantity=item['quantity'],
                            price=item['price']
                        )
                        db.session.add(order_item)

                    db.session.commit()

                    if session.get('session_active'):
                        # Adjust session revenue
                        session['session_revenue'] += total_amount
                        log_id = session.get('session_log_id')
                        if log_id:
                            log = SessionLog.query.get(log_id)
                            if log:
                                log.total_revenue += total_amount
                                db.session.commit()

                    flash('Order updated successfully!', 'success')

                    if action == 'print_kitchen':
                        # Generate Kitchen Invoice
                        return redirect(url_for('print_kitchen_invoice', order_id=order.id))
                    else:
                        return redirect(url_for('orders'))
                else:
                    # Creating a new order
                    new_order = Order(
                        table_id=table_id,
                        address=address,
                        contact_number=contact_number,
                        first_name=first_name,
                        last_name=last_name,
                        user_id=current_user.id,
                        total_amount=total_amount,
                        status='Pending'
                    )
                    db.session.add(new_order)
                    db.session.commit()

                    for ot_name in selected_order_types:
                        ot = OrderType.query.filter_by(name=ot_name).first()
                        if ot:
                            new_order.order_types.append(ot)

                    db.session.commit()

                    for item in processed_cart:
                        order_item = OrderItem(
                            order_id=new_order.id,
                            product_id=item['id'],
                            quantity=item['quantity'],
                            price=item['price']
                        )
                        db.session.add(order_item)

                    db.session.commit()

                    if session.get('session_active'):
                        session['session_orders'] = session.get('session_orders', 0) + 1
                        session['session_revenue'] = session.get('session_revenue', 0.0) + total_amount

                        log_id = session.get('session_log_id')
                        if log_id:
                            log = SessionLog.query.get(log_id)
                            if log:
                                log.total_orders += 1
                                log.total_revenue += total_amount
                                db.session.commit()

                    flash('Order placed successfully!', 'success')

                    if action == 'print_kitchen':
                        return redirect(url_for('print_kitchen_invoice', order_id=new_order.id))
                    else:
                        return redirect(url_for('orders'))

            except Exception as e:
                db.session.rollback()
                flash(f'Error placing/updating order: {e}', 'danger')
                return redirect(url_for('orders'))
        else:
            flash('Please correct the errors in the form.', 'danger')
            return redirect(url_for('orders'))

    return render_template('orders.html', form=form, products=products, categories=categories, orders=pending_orders)

# --------------------------------------------------
# Pending Bills Route
# --------------------------------------------------
@app.route('/pending_bills')
@login_required
@roles_required('admin', 'cashier')
def pending_bills():
    try:
        pending_orders = Order.query.filter_by(status='Pending').order_by(Order.date_ordered.desc()).all()
    except Exception as e:
        flash(f'Error fetching pending bills: {e}', 'danger')
        pending_orders = []
    return render_template('pending_bills.html', orders=pending_orders)

# --------------------------------------------------
# Order Details Route
# --------------------------------------------------
@app.route('/order_details/<int:order_id>', methods=['GET'])
@login_required
@roles_required('admin', 'cashier')
def order_details(order_id):
    try:
        order = Order.query.get_or_404(order_id)
        order_data = {
            'id': order.id,
            'order_type_list': [ot.name for ot in order.order_types],
            'table_id': order.table.table_number if order.table else '',
            'first_name': order.first_name if any(ot.name == 'Delivery' for ot in order.order_types) else '',
            'last_name': order.last_name if any(ot.name == 'Delivery' for ot in order.order_types) else '',
            'address': order.address if any(ot.name == 'Delivery' for ot in order.order_types) else '',
            'contact_number': order.contact_number if any(ot.name in ['Delivery', 'Takeaway'] for ot in order.order_types) else '',
            'cart': [{
                'id': item.product_id,
                'name': item.product.name,
                'price': item.price,
                'quantity': item.quantity
            } for item in order.order_items]
        }
        return jsonify(order_data)
    except Exception as e:
        flash(f'Error fetching order details: {e}', 'danger')
        return jsonify({'error': 'Failed to fetch order details.'}), 500

# --------------------------------------------------
# Complete Order Route
# --------------------------------------------------
@app.route('/complete_order/<int:order_id>', methods=['POST'])
@login_required
@roles_required('admin', 'cashier')
def complete_order(order_id):
    form = OrderForm()
    if form.validate_on_submit():
        try:
            order = Order.query.get_or_404(order_id)
            if order.status != 'Pending':
                flash('Only pending orders can be completed.', 'warning')
                return jsonify({'success': False, 'message': 'Order is not pending.'}), 400
            order.status = 'Completed'
            db.session.commit()
            flash('Order marked as completed.', 'success')
            return jsonify({'success': True, 'message': 'Order completed successfully.'})
        except Exception as e:
            db.session.rollback()
            flash(f'Error completing order: {e}', 'danger')
            return jsonify({'success': False, 'message': 'Error completing order.'}), 500
    else:
        flash('Invalid form submission.', 'danger')
        return jsonify({'success': False, 'message': 'Invalid form submission.'}), 400

# --------------------------------------------------
# Cancel Order Route
# --------------------------------------------------
@app.route('/cancel_order/<int:order_id>', methods=['POST'])
@login_required
@roles_required('admin', 'cashier')
def cancel_order(order_id):
    form = OrderForm()
    if form.validate_on_submit():
        try:
            order = Order.query.get_or_404(order_id)
            if order.status != 'Pending':
                flash('Only pending orders can be cancelled.', 'warning')
                return redirect(url_for('pending_bills'))
            for item in order.order_items:
                product = Product.query.get(item.product_id)
                if product:
                    product.stock += item.quantity
            order.status = 'Cancelled'
            db.session.commit()
            flash('Order cancelled successfully!', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error cancelling order: {e}', 'danger')
    else:
        flash('Invalid form submission.', 'danger')
    return redirect(url_for('pending_bills'))

# --------------------------------------------------
# Print Kitchen Invoice Route
# --------------------------------------------------
@app.route('/print_kitchen_invoice/<int:order_id>')
@login_required
@roles_required('admin', 'cashier')
def print_kitchen_invoice(order_id):
    try:
        order = Order.query.get_or_404(order_id)
    except Exception as e:
        flash(f'Error fetching order for printing: {e}', 'danger')
        return redirect(url_for('pending_bills'))
    return render_template('print_kitchen_invoice.html', order=order)

# --------------------------------------------------
# Print Order Route
# --------------------------------------------------
@app.route('/print_order/<int:order_id>')
@login_required
@roles_required('admin', 'cashier')
def print_order(order_id):
    try:
        order = Order.query.get_or_404(order_id)
    except Exception as e:
        flash(f'Error fetching order for printing: {e}', 'danger')
        return redirect(url_for('pending_bills'))
    return render_template('print_order.html', order=order)

# --------------------------------------------------
# Sales Report Route
# --------------------------------------------------
@app.route('/sales_report', methods=['GET', 'POST'])
@login_required
@roles_required('admin')
def sales_report():
    form = SalesReportForm(request.args)
    if form.validate():
        start_date = form.start_date.data
        end_date = form.end_date.data
        order_type = form.order_type.data
    else:
        start_date = None
        end_date = None
        order_type = 'All'

    try:
        sales_query = db.session.query(
            func.date(Order.date_ordered).label('date'),
            func.sum(Order.total_amount).label('daily_total')
        )
        if start_date:
            sales_query = sales_query.filter(Order.date_ordered >= start_date)
        if end_date:
            sales_query = sales_query.filter(Order.date_ordered <= end_date)
        if order_type != 'All':
            sales_query = sales_query.filter(Order.order_types.any(OrderType.name == order_type))
        sales = sales_query.group_by(func.date(Order.date_ordered)).all()

        sales_trends_query = db.session.query(
            func.date(Order.date_ordered).label('date'),
            func.sum(Order.total_amount).label('total_sales')
        ).filter(
            Order.date_ordered >= start_date if start_date else True,
            Order.date_ordered <= end_date if end_date else True,
            Order.order_types.any(OrderType.name == order_type) if order_type != 'All' else True
        ).group_by(
            func.date(Order.date_ordered)
        ).order_by(
            func.date(Order.date_ordered)
        )
        sales_trends = sales_trends_query.all()

        category_sales_query = db.session.query(
            Category.name.label('category_name'),
            func.sum(OrderItem.quantity * OrderItem.price).label('total_sales')
        ).select_from(OrderItem).join(Product).join(Category).join(Order)
        if start_date:
            category_sales_query = category_sales_query.filter(Order.date_ordered >= start_date)
        if end_date:
            category_sales_query = category_sales_query.filter(Order.date_ordered <= end_date)
        if order_type != 'All':
            category_sales_query = category_sales_query.filter(Order.order_types.any(OrderType.name == order_type))
        category_sales = category_sales_query.group_by(Category.name).all()

        top_products_query = db.session.query(
            Product.name.label('product_name'),
            func.sum(OrderItem.quantity * OrderItem.price).label('total_sales')
        ).join(OrderItem).join(Order).group_by(Product.name)\
          .order_by(func.sum(OrderItem.quantity * OrderItem.price).desc()).limit(10)
        if start_date:
            top_products_query = top_products_query.filter(Order.date_ordered >= start_date)
        if end_date:
            end_date_obj = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1) - timedelta(seconds=1)
            top_products_query = top_products_query.filter(Order.date_ordered <= end_date_obj)
        if order_type != 'All':
            top_products_query = top_products_query.filter(Order.order_types.any(OrderType.name == order_type))
        top_products = top_products_query.all()

    except Exception as e:
        flash(f'Error generating sales report: {e}', 'danger')
        sales = []
        sales_trends = []
        category_sales = []
        top_products = []

    start_session_form = StartSessionForm()
    end_session_form = EndSessionForm()

    return render_template(
        'sales_report.html',
        form=form,
        sales=sales,
        sales_trends=sales_trends,
        category_sales=category_sales,
        top_products=top_products,
        start_date=start_date.strftime('%Y-%m-%d') if start_date else '',
        end_date=end_date.strftime('%Y-%m-%d') if end_date else '',
        order_type=order_type,
        start_session_form=start_session_form,
        end_session_form=end_session_form
    )

# --------------------------------------------------
# Export Sales Report Route
# --------------------------------------------------
@app.route('/export_sales', methods=['GET'])
@login_required
@roles_required('admin')
def export_sales():
    export_format = request.args.get('export_format')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    order_type = request.args.get('order_type', 'All')

    try:
        sales_query = db.session.query(
            func.date(Order.date_ordered).label('date'),
            func.sum(Order.total_amount).label('daily_total')
        )
        if start_date:
            start_date_obj = datetime.strptime(start_date, '%Y-%m-%d')
            sales_query = sales_query.filter(Order.date_ordered >= start_date_obj)
        if end_date:
            end_date_obj = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1) - timedelta(seconds=1)
            sales_query = sales_query.filter(Order.date_ordered <= end_date_obj)
        if order_type != 'All':
            sales_query = sales_query.filter(Order.order_types.any(OrderType.name == order_type))
        sales = sales_query.group_by(func.date(Order.date_ordered)).all()
    except ValueError:
        flash('Invalid date format. Use YYYY-MM-DD.', 'danger')
        return redirect(url_for('sales_report'))
    except Exception as e:
        flash(f'Error exporting sales report: {e}', 'danger')
        return redirect(url_for('sales_report'))

    if export_format == 'csv':
        try:
            output = StringIO()
            writer = csv.writer(output)
            writer.writerow(['Date', 'Total Sales (Rs)'])
            for sale in sales:
                writer.writerow([sale.date, f"Rs{sale.daily_total:.2f}"])
            response = make_response(output.getvalue())
            response.headers['Content-Disposition'] = 'attachment; filename=sales_report.csv'
            response.headers['Content-Type'] = 'text/csv'
            return response
        except Exception as e:
            flash(f'Error generating CSV: {e}', 'danger')
            return redirect(url_for('sales_report'))
    elif export_format == 'pdf':
        try:
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font('Arial', 'B', 16)
            pdf.cell(0, 10, 'Sales Report', ln=True, align='C')
            pdf.ln(10)
            pdf.set_font('Arial', 'B', 12)
            pdf.cell(60, 10, 'Date', 1, 0, 'C')
            pdf.cell(60, 10, 'Total Sales (Rs)', 1, 1, 'C')
            pdf.set_font('Arial', '', 12)
            for sale in sales:
                pdf.cell(60, 10, str(sale.date), 1, 0, 'C')
                pdf.cell(60, 10, f"Rs{sale.daily_total:.2f}", 1, 1, 'C')
            pdf_output = pdf.output(dest='S').encode('latin1')
            response = make_response(pdf_output)
            response.headers['Content-Disposition'] = 'attachment; filename=sales_report.pdf'
            response.headers['Content-Type'] = 'application/pdf'
            return response
        except Exception as e:
            flash(f'Error generating PDF: {e}', 'danger')
            return redirect(url_for('sales_report'))
    else:
        flash('Invalid export format.', 'danger')
        return redirect(url_for('sales_report'))

# --------------------------------------------------
# Error Handlers
# --------------------------------------------------
@app.errorhandler(404)
def page_not_found(e):
    flash('Page not found.', 'warning')
    return render_template('404.html'), 404

@app.errorhandler(403)
def forbidden(e):
    flash('You do not have permission to access this resource.', 'danger')
    return render_template('403.html'), 403

@app.errorhandler(500)
def internal_error(e):
    db.session.rollback()
    flash('An internal error occurred. Please try again later.', 'danger')
    return render_template('500.html'), 500

# --------------------------------------------------
# Run the App
# --------------------------------------------------
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)

