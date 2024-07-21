from flask import Flask, render_template, request, send_file
import whois
import io
from reportlab.pdfgen import canvas
import concurrent.futures

app = Flask(__name__)

EXTENSIONS = ['.com', '.net', '.org', '.info', '.io']

def check_domain_availability(domain_name):
    try:
        domain_info = whois.whois(domain_name)
        if domain_info.status is None or 'No match for' in domain_info.text:
            return True
        return False
    except whois.parser.PywhoisError:
        return True  # Treat any parsing errors as the domain being available
    except Exception as e:
        return False  # Treat other exceptions as the domain being unavailable

def format_domain(domain_name):
    # If no extension is provided, default to ".com"
    if '.' not in domain_name:
        domain_name += '.com'
    return domain_name

def check_multiple_extensions(domain_name_base):
    results = {}
    with concurrent.futures.ThreadPoolExecutor() as executor:
        future_to_domain = {executor.submit(check_domain_availability, domain_name_base + ext): ext for ext in EXTENSIONS}
        for future in concurrent.futures.as_completed(future_to_domain):
            ext = future_to_domain[future]
            domain_name = domain_name_base + ext
            try:
                available = future.result()
                results[domain_name] = available
            except Exception as exc:
                results[domain_name] = False
    return results

@app.route('/', methods=['GET', 'POST'])
def index():
    results = None
    specific_domain_result = None
    if request.method == 'POST':
        domain_name = request.form['domain_name']
        if domain_name:
            domain_name = domain_name.replace(" ", "")  # Remove any spaces
            if '.' in domain_name:
                # User provided a specific domain
                specific_domain_result = {
                    'domain': domain_name,
                    'available': check_domain_availability(domain_name)
                }
            else:
                # User did not provide a specific domain, check multiple extensions
                domain_name_base = domain_name.split('.')[0]  # Remove any existing extension
                results = check_multiple_extensions(domain_name_base)
    return render_template('index.html', results=results, specific_domain_result=specific_domain_result)

@app.route('/export', methods=['POST'])
def export():
    domain_results = request.form.get('results')
    domain_results = eval(domain_results)  # Convert string back to dictionary
    
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer)
    c.drawString(100, 750, "Domain Availability Results")
    y = 720
    for domain, is_available in domain_results.items():
        c.drawString(100, y, f"{domain}: {'Available' if is_available else 'Unavailable'}")
        y -= 20
    c.save()
    
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name="domain_results.pdf", mimetype='application/pdf')

if __name__ == '__main__':
    app.run(debug=True)
