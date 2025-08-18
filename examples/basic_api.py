"""
Basic API Example
This is a simple REST API built with WebSpark that demonstrates:
- Basic routing
- GET and POST methods
- JSON responses
- Simple data storage (in-memory)
"""

from webspark.core import View, WebSpark, path
from webspark.http import JsonResponse
from webspark.utils import HTTPException

# In-memory storage for our examples
items = [
    {"id": 1, "name": "Item 1", "description": "First item"},
    {"id": 2, "name": "Item 2", "description": "Second item"},
]
next_id = 3


class ItemsView(View):
    """Handle operations on the collection of items."""

    def handle_get(self, request):
        """Return all items."""
        return JsonResponse({"items": items})

    def handle_post(self, request):
        """Create a new item."""
        global next_id
        data = request.body

        # Simple validation
        if not data or "name" not in data:
            raise HTTPException("Name is required", status_code=400)

        # Create new item
        new_item = {
            "id": next_id,
            "name": data["name"],
            "description": data.get("description", ""),
        }
        items.append(new_item)
        next_id += 1

        return JsonResponse(new_item, status=201)


class ItemDetailView(View):
    """Handle operations on a single item."""

    def handle_get(self, request):
        """Return a specific item by ID."""
        item_id = int(request.path_params["id"])
        item = next((item for item in items if item["id"] == item_id), None)

        if not item:
            raise HTTPException("Item not found", status_code=404)

        return JsonResponse(item)

    def handle_put(self, request):
        """Update a specific item."""
        item_id = int(request.path_params["id"])
        data = request.body

        # Find the item
        item_index = next(
            (i for i, item in enumerate(items) if item["id"] == item_id), None
        )
        if item_index is None:
            raise HTTPException("Item not found", status_code=404)

        # Update the item
        items[item_index]["name"] = data.get("name", items[item_index]["name"])
        items[item_index]["description"] = data.get(
            "description", items[item_index]["description"]
        )

        return JsonResponse(items[item_index])

    def handle_delete(self, request):
        """Delete a specific item."""
        global items
        item_id = int(request.path_params["id"])

        # Find and remove the item
        item = next((item for item in items if item["id"] == item_id), None)
        if not item:
            raise HTTPException("Item not found", status_code=404)

        items = [item for item in items if item["id"] != item_id]
        return JsonResponse({"message": "Item deleted"}, status=204)


# Create the app
app = WebSpark(debug=True)

# Add routes
app.add_paths(
    [
        path("/items", view=ItemsView.as_view()),
        path("/items/:id", view=ItemDetailView.as_view()),
    ]
)

if __name__ == "__main__":
    # For development purposes, you can run this with a WSGI server like:
    # gunicorn examples.basic_api:app
    print("Basic API Example")
    print("Run with: gunicorn examples.basic_api:app")
