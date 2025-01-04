/**
 * Simple function to open the browser's print dialog.
 * 
 * Usage:
 * 1. Include this script in your base layout or specific template:
 *    <script src="{{ url_for('static', filename='js/print.js') }}"></script>
 * 2. Add an onclick handler to any button or link:
 *    <button onclick="printPage()">Print</button>
 */

function printPage() {
  window.print();
}

