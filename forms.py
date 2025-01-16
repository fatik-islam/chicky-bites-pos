# forms.py

from flask_wtf import FlaskForm
from wtforms import (
    StringField, PasswordField, SubmitField,
    FloatField, IntegerField, SelectField,
    SelectMultipleField, HiddenField, DateField, FormField, FieldList, Form
)
from wtforms.validators import (
    DataRequired, Length, NumberRange,
    EqualTo, ValidationError, Optional
)
from models import Category, User, Product, Table


class LoginForm(FlaskForm):
    username = StringField('Username', validators=[
        DataRequired(message="Username is required"),
        Length(min=3, max=50, message="Username must be between 3 and 50 characters")
    ])
    password = PasswordField('Password', validators=[
        DataRequired(message="Password is required"),
        Length(min=6, message="Password must be at least 6 characters long")
    ])
    submit = SubmitField('Login')


class RegistrationForm(FlaskForm):
    username = StringField('Username', validators=[
        DataRequired(message="Username is required"),
        Length(min=4, max=150, message="Username must be between 4 and 150 characters")
    ])
    password = PasswordField('Password', validators=[
        DataRequired(message="Password is required"),
        Length(min=6, message="Password must be at least 6 characters long")
    ])
    confirm_password = PasswordField('Confirm Password', validators=[
        DataRequired(message="Please confirm your password"),
        EqualTo('password', message='Passwords must match.')
    ])
    role = SelectField('Role', choices=[('admin', 'Admin'), ('cashier', 'Cashier')], validators=[
        DataRequired(message="Please select a role")
    ])
    submit = SubmitField('Register')

    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError("Username already exists. Please choose a different one.")


class CategoryForm(FlaskForm):
    name = StringField('Category Name', validators=[
        DataRequired(message="Category name is required"),
        Length(min=2, max=100, message="Category name must be between 2 and 100 characters")
    ])
    submit = SubmitField('Add Category')

    def validate_name(self, field):
        existing = Category.query.filter_by(name=field.data).first()
        if existing:
            raise ValidationError("This category already exists.")


class TableForm(FlaskForm):
    table_number = StringField('Table Number', validators=[
        DataRequired(message="Table number is required"),
        Length(min=1, max=50, message="Table number must be between 1 and 50 characters")
    ])
    submit = SubmitField('Add Table')

    def validate_table_number(self, field):
        existing = Table.query.filter_by(table_number=field.data).first()
        if existing:
            raise ValidationError("This table number already exists.")


class ProductComponentForm(Form):
    sub_product_id = SelectField('Sub Product', coerce=int, validators=[DataRequired()])
    quantity = IntegerField('Quantity', validators=[DataRequired(), NumberRange(min=1)])


class MainProductForm(FlaskForm):
    name = StringField('Product Name', validators=[
        DataRequired(message="Product name is required"),
        Length(min=2, max=150, message="Product name must be between 2 and 150 characters")
    ])
    price = FloatField('Price (Rs)', validators=[
        DataRequired(message="Price is required"),
        NumberRange(min=0.01, message="Price must be greater than 0")
    ])
    category_id = SelectField('Category', coerce=int, validators=[
        DataRequired(message="Please select a category")
    ])
    components = FieldList(FormField(ProductComponentForm), min_entries=0, max_entries=10)
    submit = SubmitField('Add Main Product')

    def __init__(self, *args, **kwargs):
        super(MainProductForm, self).__init__(*args, **kwargs)
        self.category_id.choices = [(c.id, c.name) for c in Category.query.order_by('name').all()]
        sub_product_choices = [(0, 'Select Sub-Product')] + [(p.id, p.name) for p in Product.query.filter_by(is_sub_product=True).order_by(Product.name).all()]
        for component in self.components:
            component.sub_product_id.choices = sub_product_choices

    def validate_components(self, field):
        for component in field.entries:
            if component.sub_product_id.data == 0:
                raise ValidationError("Please select a valid sub-product.")


class SubProductForm(FlaskForm):
    name = StringField('Sub-Product Name', validators=[
        DataRequired(message="Sub-Product name is required"),
        Length(min=2, max=150, message="Sub-Product name must be between 2 and 150 characters")
    ])
    stock = IntegerField('Stock Quantity', validators=[
        DataRequired(message="Stock quantity is required"),
        NumberRange(min=0, message="Stock must be a non-negative integer")
    ])
    submit = SubmitField('Add Sub-Product')

    def validate_name(self, field):
        existing_product = Product.query.filter_by(name=field.data).first()
        if existing_product:
            raise ValidationError("A product with this name already exists. Please choose a different name.")


class OrderForm(FlaskForm):
    order_type = SelectMultipleField('Order Type', choices=[
        ('Dine-in', 'Dine-in'),
        ('Takeaway', 'Takeaway'),
        ('Delivery', 'Delivery')
    ], validators=[DataRequired(message="Please select at least one order type")])
    
    table_id = SelectField('Table Number', coerce=int, validators=[
        Optional()
    ])
    
    address = StringField('Address', validators=[
        Optional(),
        Length(max=255, message="Address cannot exceed 255 characters")
    ])
    
    contact_number = StringField('Contact Number', validators=[
        Optional(),
        Length(max=20, message="Contact number cannot exceed 20 characters")
    ])
    
    first_name = StringField('First Name', validators=[
        Optional(),
        Length(max=100, message="First name cannot exceed 100 characters")
    ])
    
    last_name = StringField('Last Name', validators=[
        Optional(),
        Length(max=100, message="Last name cannot exceed 100 characters")
    ])
    
    cart = HiddenField('Cart', validators=[DataRequired(message="Cart data is required")])
    
    submit = SubmitField('Place Order')

    def __init__(self, *args, **kwargs):
        super(OrderForm, self).__init__(*args, **kwargs)
        self.table_id.choices = [(0, 'Select Table')] + [(t.id, t.table_number) for t in Table.query.order_by('table_number').all()]

    def validate(self):
        rv = FlaskForm.validate(self)
        if not rv:
            return False

        selected_order_types = self.order_type.data

        if 'Dine-in' in selected_order_types:
            if not self.table_id.data or self.table_id.data == 0:
                self.table_id.errors.append("Table number is required for Dine-in orders.")
                return False
        if 'Delivery' in selected_order_types:
            if not self.address.data:
                self.address.errors.append("Address is required for Delivery orders.")
                return False
            if not self.contact_number.data:
                self.contact_number.errors.append("Contact number is required for Delivery orders.")
                return False
            if not self.first_name.data or not self.last_name.data:
                self.first_name.errors.append("First and Last names are required for Delivery orders.")
                self.last_name.errors.append("First and Last names are required for Delivery orders.")
                return False
        if 'Takeaway' in selected_order_types:
            if not self.contact_number.data:
                self.contact_number.errors.append("Contact number is required for Takeaway orders.")
                return False

        return True


class SalesReportForm(FlaskForm):
    start_date = StringField('Start Date (YYYY-MM-DD)', validators=[Optional(), Length(min=10, max=10, message="Start date must be in YYYY-MM-DD format")])
    end_date = StringField('End Date (YYYY-MM-DD)', validators=[Optional(), Length(min=10, max=10, message="End date must be in YYYY-MM-DD format")])
    order_type = SelectField('Order Type', choices=[
        ('All', 'All'),
        ('Dine-in', 'Dine-in'),
        ('Takeaway', 'Takeaway'),
        ('Delivery', 'Delivery')
    ], validators=[DataRequired(message="Please select an order type")])
    submit = SubmitField('Generate Report')


class ChangePasswordForm(FlaskForm):
    current_password = PasswordField('Current Password', validators=[
        DataRequired(message="Current password is required")
    ])
    new_password = PasswordField('New Password', validators=[
        DataRequired(message="New password is required"),
        Length(min=6, message="Password must be at least 6 characters long")
    ])
    confirm_new_password = PasswordField('Confirm New Password', validators=[
        DataRequired(message="Please confirm your new password"),
        EqualTo('new_password', message='Passwords must match.')
    ])
    submit = SubmitField('Change Password')


class StartSessionForm(FlaskForm):
    submit = SubmitField('Start Session')


class EndSessionForm(FlaskForm):
    submit = SubmitField('End Session')

