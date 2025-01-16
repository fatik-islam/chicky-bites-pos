# models.py

from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
import json

db = SQLAlchemy()

# Association table between Order and OrderType
order_order_types = db.Table('order_order_types',
    db.Column('order_id', db.Integer, db.ForeignKey('order.id'), primary_key=True),
    db.Column('order_type_id', db.Integer, db.ForeignKey('order_type.id'), primary_key=True)
)

class OrderType(db.Model):
    __tablename__ = 'order_type'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False, unique=True)
    
    orders = db.relationship('Order', secondary=order_order_types, back_populates='order_types')
    
    def __repr__(self):
        return f'<OrderType {self.name}>'

class ProductComponent(db.Model):
    __tablename__ = 'product_components'
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), primary_key=True)
    sub_product_id = db.Column(db.Integer, db.ForeignKey('product.id'), primary_key=True)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    
    product = db.relationship('Product', foreign_keys=[product_id], back_populates='component_associations')
    sub_product = db.relationship('Product', foreign_keys=[sub_product_id], back_populates='used_in_associations')
    
    def __repr__(self):
        return f'<ProductComponent Product ID: {self.product_id}, Sub-Product ID: {self.sub_product_id}, Quantity: {self.quantity}>'

class User(UserMixin, db.Model):
    __tablename__ = 'user'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), nullable=False, unique=True)
    password = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(50), nullable=False)
    
    session_logs = db.relationship('SessionLog', backref='user', lazy=True)
    orders = db.relationship('Order', backref='user', lazy=True)
    
    def __repr__(self):
        return f'<User {self.username}>'

class Category(db.Model):
    __tablename__ = 'category'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False, unique=True)
    
    products = db.relationship('Product', backref='category', lazy=True)
    
    def __repr__(self):
        return f'<Category {self.name}>'

class Table(db.Model):
    __tablename__ = 'table'

    id = db.Column(db.Integer, primary_key=True)
    table_number = db.Column(db.String(50), nullable=False, unique=True)  # Separate table numbers
    
    def __repr__(self):
        return f'<Table {self.table_number}>'

class Product(db.Model):
    __tablename__ = 'product'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False, unique=True)
    price = db.Column(db.Float, nullable=False)
    stock = db.Column(db.Integer, nullable=False, default=0)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=True)
    is_sub_product = db.Column(db.Boolean, nullable=False, default=False)
    
    component_associations = db.relationship(
        'ProductComponent',
        foreign_keys=[ProductComponent.product_id],
        back_populates='product',
        cascade='all, delete-orphan'
    )
    used_in_associations = db.relationship(
        'ProductComponent',
        foreign_keys=[ProductComponent.sub_product_id],
        back_populates='sub_product',
        cascade='all, delete-orphan'
    )
    order_items = db.relationship('OrderItem', backref='product', lazy=True)

    def __repr__(self):
        return f'<Product {self.name}>'

class Order(db.Model):
    __tablename__ = 'order'

    id = db.Column(db.Integer, primary_key=True)
    table_id = db.Column(db.Integer, db.ForeignKey('table.id'), nullable=True)
    address = db.Column(db.String(255), nullable=True)
    contact_number = db.Column(db.String(20), nullable=True)
    first_name = db.Column(db.String(100), nullable=True)
    last_name = db.Column(db.String(100), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    total_amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(50), nullable=False, default='Pending')
    date_ordered = db.Column(db.DateTime, nullable=False, default=db.func.current_timestamp())
    
    order_items = db.relationship('OrderItem', backref='order', lazy=True)
    
    table = db.relationship('Table', backref='orders')

    # Many-to-Many relationship with OrderType
    order_types = db.relationship('OrderType', secondary=order_order_types, back_populates='orders')

    def __repr__(self):
        return f'<Order {self.id} - {", ".join([ot.name for ot in self.order_types])}>'

    def to_json(self):
        return json.dumps({
            'id': self.id,
            'order_type_list': [ot.name for ot in self.order_types],
            'table_id': self.table_id,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'address': self.address,
            'contact_number': self.contact_number,
            'cart': [
                {
                    'id': item.product_id,
                    'name': item.product.name,
                    'price': item.price,
                    'quantity': item.quantity
                } for item in self.order_items
            ]
        })

class OrderItem(db.Model):
    __tablename__ = 'order_item'

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    price = db.Column(db.Float, nullable=False)

    def __repr__(self):
        return f'<OrderItem {self.id} - Product ID: {self.product_id}>'

class SessionLog(db.Model):
    __tablename__ = 'session_log'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=True)
    total_orders = db.Column(db.Integer, nullable=False, default=0)
    total_revenue = db.Column(db.Float, nullable=False, default=0.0)
    
    def __repr__(self):
        return f'<SessionLog {self.id} - User ID: {self.user_id}>'

