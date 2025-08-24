"""
Database Integration Example
This example demonstrates integrating WebSpark with a database:
- Using SQLite
- CRUD operations with database models
- Error handling for database operations
"""

import sqlite3
from contextlib import contextmanager

from webspark.core import View, WebSpark, path
from webspark.http import Context
from webspark.utils import HTTPException

# Database configuration
DB_NAME = "/tmp/example.db"


# Initialize database
def init_db():
    """Create the database and tables if they don't exist."""
    with get_db_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                price INTEGER NOT NULL,  -- Store in cents to avoid floating point issues
                category TEXT NOT NULL
            )
        """)
        conn.commit()


@contextmanager
def get_db_connection():
    """Context manager for database connections."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row  # This allows us to access columns by name
    try:
        yield conn
    finally:
        conn.close()


class ProductListView(View):
    """Handle operations on the collection of products."""

    def handle_get(self, ctx: Context):
        """Return all products."""
        category = ctx.query_params.get("category")

        with get_db_connection() as conn:
            if category:
                cursor = conn.execute(
                    "SELECT * FROM products WHERE category = ?", (category,)
                )
            else:
                cursor = conn.execute("SELECT * FROM products")
            products = [dict(row) for row in cursor.fetchall()]

        # Convert price from cents to dollars for display
        for product in products:
            product["price_dollars"] = product["price"] / 100

        ctx.json({"products": products})

    def handle_post(self, ctx: Context):
        """Create a new product."""
        data = ctx.body

        # Simple validation
        required_fields = ["name", "price", "category"]
        for field in required_fields:
            if field not in data:
                raise HTTPException(f"{field} is required", status_code=400)

        # Convert price to cents
        try:
            price_cents = int(float(data["price"]) * 100)
            if price_cents <= 0:
                raise ValueError()
        except (ValueError, TypeError) as e:
            raise HTTPException(
                "Price must be a positive number", status_code=400
            ) from e

        with get_db_connection() as conn:
            try:
                cursor = conn.execute(
                    """
                    INSERT INTO products (name, description, price, category)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        data["name"],
                        data.get("description", ""),
                        price_cents,
                        data["category"],
                    ),
                )
                conn.commit()
                product_id = cursor.lastrowid
            except sqlite3.Error as e:
                raise HTTPException(f"Database error: {str(e)}", status_code=500) from e

        # Return the created product
        with get_db_connection() as conn:
            cursor = conn.execute("SELECT * FROM products WHERE id = ?", (product_id,))
            product = dict(cursor.fetchone())

        # Convert price from cents to dollars for display
        product["price_dollars"] = product["price"] / 100

        ctx.json(product, status=201)


class ProductDetailView(View):
    """Handle operations on a single product."""

    def handle_get(self, ctx: Context):
        """Return a specific product by ID."""
        try:
            product_id = int(ctx.path_params["id"])
        except (ValueError, KeyError) as e:
            raise HTTPException("Invalid product ID", status_code=400) from e

        with get_db_connection() as conn:
            cursor = conn.execute("SELECT * FROM products WHERE id = ?", (product_id,))
            row = cursor.fetchone()
            if not row:
                raise HTTPException("Product not found", status_code=404)
            product = dict(row)

        # Convert price from cents to dollars for display
        product["price_dollars"] = product["price"] / 100

        ctx.json(product)

    def handle_put(self, ctx: Context):
        """Update a specific product."""
        try:
            product_id = int(ctx.path_params["id"])
        except (ValueError, KeyError) as e:
            raise HTTPException("Invalid product ID", status_code=400) from e

        data = ctx.body

        # Check if product exists
        with get_db_connection() as conn:
            cursor = conn.execute("SELECT id FROM products WHERE id = ?", (product_id,))
            if not cursor.fetchone():
                raise HTTPException("Product not found", status_code=404)

        # Build update query dynamically
        update_fields = []
        values = []

        if "name" in data:
            update_fields.append("name = ?")
            values.append(data["name"])

        if "description" in data:
            update_fields.append("description = ?")
            values.append(data.get("description", ""))

        if "price" in data:
            try:
                price_cents = int(float(data["price"]) * 100)
                if price_cents <= 0:
                    raise ValueError()
                update_fields.append("price = ?")
                values.append(price_cents)
            except (ValueError, TypeError) as e:
                raise HTTPException(
                    "Price must be a positive number", status_code=400
                ) from e

        if "category" in data:
            update_fields.append("category = ?")
            values.append(data["category"])

        if not update_fields:
            raise HTTPException("No valid fields to update", status_code=400)

        # Add product_id to values for WHERE clause
        values.append(product_id)

        # Update the product
        with get_db_connection() as conn:
            try:
                conn.execute(
                    f"UPDATE products SET {', '.join(update_fields)} WHERE id = ?",
                    values,
                )
                conn.commit()
            except sqlite3.Error as e:
                raise HTTPException(f"Database error: {str(e)}", status_code=500) from e

        # Return the updated product
        with get_db_connection() as conn:
            cursor = conn.execute("SELECT * FROM products WHERE id = ?", (product_id,))
            product = dict(cursor.fetchone())

        # Convert price from cents to dollars for display
        product["price_dollars"] = product["price"] / 100

        ctx.json(product)

    def handle_delete(self, ctx: Context):
        """Delete a specific product."""
        try:
            product_id = int(ctx.path_params["id"])
        except (ValueError, KeyError) as e:
            raise HTTPException("Invalid product ID", status_code=400) from e

        with get_db_connection() as conn:
            cursor = conn.execute("SELECT id FROM products WHERE id = ?", (product_id,))
            if not cursor.fetchone():
                raise HTTPException("Product not found", status_code=404)

            conn.execute("DELETE FROM products WHERE id = ?", (product_id,))
            conn.commit()

        ctx.json({"message": "Product deleted"}, status=204)


# Create the app
app = WebSpark(debug=True)

# Initialize database
init_db()

# Add routes
app.add_paths(
    [
        path("/products", view=ProductListView.as_view()),
        path("/products/:id", view=ProductDetailView.as_view()),
    ]
)

if __name__ == "__main__":
    # For development purposes, you can run this with a WSGI server like:
    # gunicorn examples.database_example:app
    print("Database Integration Example")
    print("Run with: gunicorn examples.database_example:app")
