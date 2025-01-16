// UPDATED static/js/scripts.js

document.addEventListener('DOMContentLoaded', function () {
    // Initialize Bootstrap tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.forEach(function (tooltipTriggerEl) {
        new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // ========== ORDER TYPE LOGIC ==========
    const orderTypeToggles    = document.querySelectorAll('.order-type-toggle');
    const orderTypeFeedback   = document.getElementById('orderTypeFeedback');
    const orderTypeHiddenContainer = document.getElementById('orderTypeHiddenContainer');

    // Dine-in Modal references
    const dineInModalEl       = document.getElementById('dineInModal');
    const saveDineInDetailsBtn= document.getElementById('saveDineInDetailsBtn');
    let   dineInModal;
    if (dineInModalEl) dineInModal = new bootstrap.Modal(dineInModalEl);

    // Delivery Modal references
    const deliveryModalEl     = document.getElementById('deliveryModal');
    const saveDeliveryDetailsBtn = document.getElementById('saveDeliveryDetailsBtn');
    let   deliveryModal;
    if (deliveryModalEl) deliveryModal = new bootstrap.Modal(deliveryModalEl);

    // Hidden fields for dine-in/delivery details
    const hiddenDineInTableId     = document.getElementById('hiddenDineInTableId');
    const hiddenDeliveryFirstName = document.getElementById('hiddenDeliveryFirstName');
    const hiddenDeliveryLastName  = document.getElementById('hiddenDeliveryLastName');
    const hiddenDeliveryAddress   = document.getElementById('hiddenDeliveryAddress');
    const hiddenDeliveryContact   = document.getElementById('hiddenDeliveryContactNum');

    // Dine-in form
    const dineInForm        = document.getElementById('dineInForm');
    const dineInTableNumber = document.getElementById('dineInTableNumber');

    // Delivery form
    const deliveryForm            = document.getElementById('deliveryForm');
    const deliveryFirstName       = document.getElementById('deliveryFirstName');
    const deliveryLastName        = document.getElementById('deliveryLastName');
    const deliveryAddress         = document.getElementById('deliveryAddress');
    const deliveryContactNumber   = document.getElementById('deliveryContactNumber');

    // The function that updates hidden fields with user’s order-type selections
    function updateOrderTypeHiddenInputs() {
        // Clear old hidden inputs
        orderTypeHiddenContainer.innerHTML = '';
        // For each toggle that is checked, create an <input> type="hidden"
        orderTypeToggles.forEach(toggle => {
            if (toggle.checked) {
                let hiddenInput = document.createElement('input');
                hiddenInput.type = 'hidden';
                hiddenInput.name = 'order_type';
                hiddenInput.value= toggle.value;
                orderTypeHiddenContainer.appendChild(hiddenInput);
            }
        });
    }

    // Called whenever toggles change
    function checkOrderTypes() {
        let selectedTypes = [];
        orderTypeToggles.forEach(t => {
            if (t.checked) selectedTypes.push(t.value);
        });
        if (selectedTypes.length === 0) {
            orderTypeFeedback.style.display = 'block';
        } else {
            orderTypeFeedback.style.display = 'none';
        }
        updateOrderTypeHiddenInputs();
        // If user toggles on Dine-in => show Dine-in Modal
        if (selectedTypes.includes('Dine-in') && dineInModal) {
            dineInModal.show();
        }
        // If user toggles on Delivery => show Delivery Modal
        if (selectedTypes.includes('Delivery') && deliveryModal) {
            deliveryModal.show();
        }
    }

    // Attach event to toggles
    orderTypeToggles.forEach(toggle => {
        toggle.addEventListener('change', checkOrderTypes);
    });
    checkOrderTypes(); // initial

    // ========== DINE-IN FORM SAVE ========== 
    if (saveDineInDetailsBtn) {
        saveDineInDetailsBtn.addEventListener('click', function() {
            // Validate local form
            if (!dineInForm.checkValidity()) {
                dineInForm.classList.add('was-validated');
                return;
            }
            // If valid, store in hidden fields
            hiddenDineInTableId.value = dineInTableNumber.value;
            // Then close the modal
            if (dineInModal) dineInModal.hide();
        });
    }

    // ========== DELIVERY FORM SAVE ========== 
    if (saveDeliveryDetailsBtn) {
        saveDeliveryDetailsBtn.addEventListener('click', function() {
            // Validate local form
            if (!deliveryForm.checkValidity()) {
                deliveryForm.classList.add('was-validated');
                return;
            }
            // If valid, store in hidden fields
            hiddenDeliveryFirstName.value  = deliveryFirstName.value;
            hiddenDeliveryLastName.value   = deliveryLastName.value;
            hiddenDeliveryAddress.value    = deliveryAddress.value;
            hiddenDeliveryContact.value    = deliveryContactNumber.value;
            // Then close the modal
            if (deliveryModal) deliveryModal.hide();
        });
    }

    // ========== PRODUCT SEARCH ==========
    const productSearch   = document.getElementById('productSearch');
    const productItems    = document.querySelectorAll('.product-item');
    const noProductsEl    = document.getElementById('noProducts');

    if (productSearch) {
        productSearch.addEventListener('input', function() {
            const query = this.value.toLowerCase();
            let visibleCount = 0;
            productItems.forEach(item => {
                const titleEl = item.querySelector('.card-title');
                const name    = titleEl ? titleEl.textContent.toLowerCase() : '';
                if (name.includes(query)) {
                    item.style.display = 'block';
                    visibleCount++;
                } else {
                    item.style.display = 'none';
                }
            });
            if (visibleCount === 0 && noProductsEl) {
                noProductsEl.style.display = 'block';
            } else if (noProductsEl) {
                noProductsEl.style.display = 'none';
            }
        });
    }

    // ========== CART LOGIC ==========
    let cart = [];
    const orderTableBody = document.querySelector('#orderTable tbody');
    const subTotalEl     = document.getElementById('subTotal');
    const gstAmountEl    = document.getElementById('gstAmount');
    const netAmountEl    = document.getElementById('netAmount');
    const cartInput      = document.getElementById('cartInput');
    const orderForm      = document.getElementById('orderForm');
    const cancelOrderBtn = document.getElementById('cancelOrderBtn');
    const emptyCartEl    = document.getElementById('emptyCart');

    // Helper to see if any type is selected
    function anyOrderTypeSelected() {
        return [...orderTypeToggles].some(t => t.checked);
    }

    // Show a simple toast
    function showToast(message, type) {
        let toastContainer = document.getElementById('toastContainer');
        if (!toastContainer) {
            toastContainer = document.createElement('div');
            toastContainer.id = 'toastContainer';
            toastContainer.className = 'toast-container position-fixed bottom-0 end-0 p-3';
            document.body.appendChild(toastContainer);
        }
        const toastEl = document.createElement('div');
        toastEl.className = `toast align-items-center text-bg-${type} border-0`;
        toastEl.setAttribute('role', 'alert');
        toastEl.setAttribute('aria-live', 'assertive');
        toastEl.setAttribute('aria-atomic', 'true');
        toastEl.innerHTML = `
            <div class="d-flex">
                <div class="toast-body">
                    ${message}
                </div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
            </div>
        `;
        toastContainer.appendChild(toastEl);
        const bsToast = new bootstrap.Toast(toastEl, { delay: 5000 });
        bsToast.show();
        toastEl.addEventListener('hidden.bs.toast', () => {
            toastEl.remove();
        });
    }

    // Render the cart
    function renderCart() {
        orderTableBody.innerHTML = '';
        let subtotal = 0;

        if (cart.length === 0) {
            if (emptyCartEl) emptyCartEl.style.display = 'block';
        } else {
            if (emptyCartEl) emptyCartEl.style.display = 'none';
        }

        cart.forEach(item => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${item.id}</td>
                <td>${item.name}</td>
                <td>
                    <input
                        type="number"
                        min="1"
                        value="${item.quantity}"
                        data-id="${item.id}"
                        class="form-control cartQty"
                        style="width:70px;"
                    >
                </td>
                <td>Rs${item.price.toFixed(2)}</td>
                <td>Rs${item.amount.toFixed(2)}</td>
                <td>
                    <button class="btn btn-sm btn-danger removeBtn" data-id="${item.id}">
                        <i class="bi bi-trash-fill"></i>
                    </button>
                </td>
            `;
            orderTableBody.appendChild(row);
            subtotal += item.amount;
        });

        document.querySelectorAll('.cartQty').forEach(input => {
            input.addEventListener('change', function(e) {
                const newQty = parseInt(e.target.value);
                const prodId = parseInt(e.target.dataset.id);
                const cartItem = cart.find(i => i.id === prodId);
                if (cartItem && newQty >= 1) {
                    cartItem.quantity = newQty;
                    cartItem.amount   = cartItem.price * newQty;
                    renderCart();
                    showToast(`${cartItem.name} quantity updated to ${newQty}.`, 'info');
                } else {
                    // revert to old value
                    e.target.value = cartItem.quantity;
                }
            });
        });

        document.querySelectorAll('.removeBtn').forEach(btn => {
            btn.addEventListener('click', function() {
                const pid = parseInt(this.dataset.id);
                cart = cart.filter(i => i.id !== pid);
                renderCart();
                showToast('Product removed from cart.', 'warning');
            });
        });

        const gstAmount = subtotal * 0.10;
        const netAmount = subtotal + gstAmount;
        subTotalEl.textContent  = subtotal.toFixed(2);
        gstAmountEl.textContent = gstAmount.toFixed(2);
        netAmountEl.textContent = netAmount.toFixed(2);
        cartInput.value         = JSON.stringify(cart);
    }

    // Clicking on product card => add to cart
    document.querySelectorAll('.product-item .card').forEach(card => {
        card.addEventListener('click', function() {
            if (!anyOrderTypeSelected()) {
                showToast('Please select at least one Order Type before adding products.', 'danger');
                return;
            }
            const parent   = card.parentElement; // the .product-item
            const prodId   = parseInt(parent.getAttribute('data-id'));
            const prodName = card.querySelector('.card-title')?.textContent.trim() || 'Unknown';
            const priceStr = parent.getAttribute('data-price') || '0';
            const prodPrice= parseFloat(priceStr);

            // Check if cart already has it
            const existingItem = cart.find(i => i.id === prodId);
            if (existingItem) {
                existingItem.quantity++;
                existingItem.amount = existingItem.quantity * existingItem.price;
            } else {
                cart.push({
                    id: prodId,
                    name: prodName,
                    price: prodPrice,
                    quantity: 1,
                    amount: prodPrice
                });
            }
            renderCart();
            showToast(`${prodName} added to cart!`, 'success');
        });
    });

    // Cancel Order
    if (cancelOrderBtn) {
        cancelOrderBtn.addEventListener('click', function() {
            if (confirm('Are you sure you want to cancel this order?')) {
                cart = [];
                renderCart();
                // Uncheck toggles & update hidden
                orderTypeToggles.forEach(t => t.checked = false);
                checkOrderTypes();
                showToast('Order has been canceled.', 'warning');
                document.getElementById('orderId').value = '';
                orderForm.classList.remove('was-validated');
            }
        });
    }

    // Validate main order form on submission
    if (orderForm) {
        orderForm.addEventListener('submit', function(event) {
            // Must have at least one order type
            if (!anyOrderTypeSelected()) {
                showToast('Please select at least one Order Type before saving/printing.', 'danger');
                event.preventDefault();
                event.stopPropagation();
                return;
            }
            // Validate normal form
            if (!orderForm.checkValidity()) {
                event.preventDefault();
                event.stopPropagation();
            }
            orderForm.classList.add('was-validated');
        });
    }

    // Update Orders - Edit existing order
    document.addEventListener('click', function(e) {
        if (e.target && e.target.classList.contains('edit-order-btn')) {
            const orderId = e.target.getAttribute('data-order-id');
            fetch(`/order_details/${orderId}`)
            .then(response => response.json())
            .then(data => {
                if (data.error) {
                    showToast(data.error, 'danger');
                    return;
                }
                // Fill main form with data
                document.getElementById('orderId').value = data.id;

                // 1) Reset toggles
                orderTypeToggles.forEach(t => t.checked = false);

                // 2) Check toggles from data
                data.order_type_list.forEach(ot => {
                    const toggle = [...orderTypeToggles].find(x => x.value === ot);
                    if (toggle) toggle.checked = true;
                });
                checkOrderTypes();

                // 3) If Dine-in included, set table
                if (data.order_type_list.includes('Dine-in')) {
                    if (dineInTableNumber) dineInTableNumber.value = data.table_id || '';
                    hiddenDineInTableId.value = data.table_id || '';
                }
                // 4) If Delivery included, fill fields
                if (data.order_type_list.includes('Delivery')) {
                    if (deliveryFirstName)     deliveryFirstName.value     = data.first_name || '';
                    if (deliveryLastName)      deliveryLastName.value      = data.last_name  || '';
                    if (deliveryAddress)       deliveryAddress.value       = data.address    || '';
                    if (deliveryContactNumber) deliveryContactNumber.value = data.contact_number || '';

                    hiddenDeliveryFirstName.value = data.first_name || '';
                    hiddenDeliveryLastName.value  = data.last_name  || '';
                    hiddenDeliveryAddress.value   = data.address    || '';
                    hiddenDeliveryContact.value   = data.contact_number || '';
                }

                // 5) Populate cart
                cart = data.cart.map(item => ({
                    id: item.id,
                    name: item.name,
                    price: parseFloat(item.price),
                    quantity: parseInt(item.quantity),
                    amount: parseFloat(item.price) * parseInt(item.quantity)
                }));
                renderCart();

                // Close updateOrderModal if open
                const updateOrderModalEl = document.getElementById('updateOrderModal');
                const updateOrderModal   = bootstrap.Modal.getInstance(updateOrderModalEl);
                if (updateOrderModal) updateOrderModal.hide();

                showToast('Order details loaded successfully.', 'info');
            })
            .catch(error => {
                console.error('Error fetching order details:', error);
                showToast('Failed to load order details.', 'danger');
            });
        }
    });
});

