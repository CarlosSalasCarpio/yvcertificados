from fileinput import filename
from urllib import response
import requests
from django.http import StreamingHttpResponse, FileResponse
from email import message
from django import forms
from django.conf import settings
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render, redirect
from django.urls import reverse
from django.contrib import messages
from .utils import csv_to_models, current_date_format, link_callback, get_blob_url 
from .models import Employees, Desprendibles
import io
import os
from django.http import HttpResponse
from django.views.generic import View
from datetime import datetime
from xhtml2pdf import pisa
from django.template.loader import get_template
import urllib.request
import re
from PyPDF2 import PdfFileReader, PdfFileWriter


# Register form
class NewUserForm(UserCreationForm):
	email = forms.EmailField(required=True, label='Correo electrónico')
	username = forms.CharField(required=True, label='Número de identificación')
	password1 = forms.CharField(label='Contraseña',
		widget=forms.PasswordInput)
	password2 = forms.CharField(label='Confirmar contraseña',
 		widget=forms.PasswordInput)

	class Meta:
		model = User
		fields = ("username", "email", "password1", "password2")

	def save(self, commit=True):
		user = super(NewUserForm, self).save(commit=False)
		user.email = self.cleaned_data['email']
		if commit:
			user.save()
		return user


# Upload CSV form
class UploadFileForm(forms.Form):
	file = forms.FileField(label=False)


# Upload PDF form
class DesprendiblesForm(forms.ModelForm):
	quincena= (
		('Primera','Primera'),
		('Segunda','Segunda'),
	)

	mes= (
		('Enero','Enero'),
		('Febrero','Febrero'),
		('Marzo','Marzo'),
		('Abril','Abril'),
		('Mayo','Mayo'),
		('Junio','Junio'),
		('Julio','Julio'),
		('Agosto','Agosto'),
		('Septiembre','Septiembre'),
		('Octubre','Octubre'),
		('Noviembre','Noviembre'),
		('Diciembre','Diciembre'),
	)

	año= (
		('2020','2020'),
		('2021','2021'),
		('2022','2022'),
		('2023','2023'),
		('2024','2024'),
		('2025','2025'),
		('2026','2026'),
		('2027','2027'),
		('2028','2028'),
		('2029','2029'),
		('2030','2030'),
	)

	quincena = forms.ChoiceField(widget=forms.Select, choices=quincena)
	mes = forms.ChoiceField(widget=forms.Select, choices=mes)
	año = forms.ChoiceField(widget=forms.Select, choices=año)

	class Meta:
		model = Desprendibles
		fields = ('quincena', 'mes', 'año', 'pdf')


# User login
def login_view(request):
	if request.method == "POST":
		username = request.POST["username"]
		password = request.POST["password"]
		user = authenticate(request, username=username, password=password)
		if user is not None:
			login(request, user)
			if not user.is_staff:
				return HttpResponseRedirect(reverse("index"))
			else:
				return HttpResponseRedirect(reverse("admin_main"))
		else:
			return render(request, "pdf_manager/login.html", {
			"message": "Credenciales incorrectas"
			})
	else:
		return render(request, "pdf_manager/login.html")


# User logout
def logout_view(request):
	logout(request)
	return HttpResponseRedirect(reverse("login"))


# New user register
def register(request):
	if request.method == "POST":
		form = NewUserForm(request.POST)
		if Employees.objects.filter(NÚMERODEIDENTIFICACIÓN = request.POST['username']).exists() == False:
			message = "Número de identificación no válido"
			return render (request, "pdf_manager/register.html", context={
				"register_form": form,
				'message': message
			})

		elif '@yvsite.com' not in str(request.POST['email']):
			message = "Correo no válido, asegurese de utilizar un correo @yvsite.com"
			return render (request, "pdf_manager/register.html", context={
				"register_form": form,
				'message': message
			})

		elif form.is_valid():
			user = form.save()
			messages.success(request, "Registration successful." )
			message = "Registro exitoso"
			return render (request, "pdf_manager/register_success.html", context={
				'message': message
			})

		else:
			message = "Información invalida"
			return render (request, "pdf_manager/register.html", context={
				"register_form": form,
				'message': message
			})

	form = NewUserForm()
	return render (request, "pdf_manager/register.html", context={
		"register_form": form
	})


# User can download pay roll (certificado)
def index(request):
	if request.method == 'GET':
		if not request.user.is_authenticated:
			return HttpResponseRedirect(reverse("login"))
		elif request.user.is_staff:
			logout(request)
			return HttpResponseRedirect(reverse("login"))
		else:
			desprendibles = Desprendibles.objects.all()
			return render(request, 'pdf_manager/user.html', {
				'username': request.user.username,
				'email': request.user.email,
				'nombre': Employees.objects.get(NÚMERODEIDENTIFICACIÓN = request.user.username).EMPLEADO,
				'desprendibles': desprendibles
			})

	elif request.method == 'POST':
		# Certificate download
		name = Employees.objects.get(NÚMERODEIDENTIFICACIÓN = request.user.username).EMPLEADO
		document_type = Employees.objects.get(NÚMERODEIDENTIFICACIÓN = request.user.username).TIPODOCUMENTO
		if document_type == "CED":
			document_type = "CC"
		elif document_type == "PAS":
			document_type = "PAS"
		else:
			document_type = "CE"
		id = request.user.username
		hire_date = Employees.objects.get(NÚMERODEIDENTIFICACIÓN = request.user.username).FECHADEINGRESO.replace("-", " de ")
		possition = Employees.objects.get(NÚMERODEIDENTIFICACIÓN = request.user.username).NOMBREDELCARGO
		contract_type = Employees.objects.get(NÚMERODEIDENTIFICACIÓN = request.user.username).TIPODECONTRATO
		salary = Employees.objects.get(NÚMERODEIDENTIFICACIÓN = request.user.username).VALORSUELDO
		company_db = Employees.objects.get(NÚMERODEIDENTIFICACIÓN = request.user.username).EMPRESA
		if "COLOMBIA SAS" in company_db:
			nit = "800035887-9"
			company = "Y&V INGENIERIA Y CONSTRUCCION COLOMBIA SAS"
		else:
			nit = "900467640-3"
			company = "Y&V INGENIERIA Y CONSTRUCCION SUCURSAL COLOMBIA"
		today = current_date_format(datetime.now())
		logo = 'pdf_manager/logo.JPG'
		firma = 'pdf_manager/firma.JPG'
		footer = 'pdf_manager/footer.JPG'

		if request.POST.get("submit_button") == "certificate":
			template_path = 'pdf_manager/certificado.html'
			context = {
				'name': name,
				'document_type': document_type,
				'id': id,
				'hire_date': hire_date,
				'possition': possition,
				'contract_type': contract_type,
				'salary': salary,
				'company': company,
				'nit': nit,
				'today': today,
				'logo': logo,
				'firma': firma,
				'footer': footer
				}
			# Create a Django response object, and specify content_type as pdf
			response = HttpResponse(content_type='application/pdf')
			response['Content-Disposition'] = 'attachment; filename="CERTIFICACIÓN_LABORAL.pdf"'
			# find the template and render it.
			template = get_template(template_path)
			html = template.render(context)

			# create a pdf
			pisa_status = pisa.CreatePDF(
				html, dest=response, link_callback=link_callback)
			return response


# HR can choose to update PDF for (desprendibles) or CSV for (certificados)
def admin_main(request):
	if request.method == 'GET':
		if not request.user.is_authenticated:
			return HttpResponseRedirect(reverse("login"))
		else:
			return render(request, 'pdf_manager/admin.html')
	elif request.method == 'POST':
		if request.POST['submit_button'] == 'csv':
			return HttpResponseRedirect(reverse("admin_csv"))
		if request.POST['submit_button'] == 'pdf':
			return HttpResponseRedirect(reverse("admin_pdf"))	


# HR can upload CSV
def admin_csv(request):
	form = UploadFileForm(request.POST, request.FILES)
	if request.method == 'GET':
		if not request.user.is_authenticated:
			return HttpResponseRedirect(reverse("login"))
		else:
			return render(request, 'pdf_manager/admin_csv.html', {
				'upload_csv_form': form
			})
	elif request.method == 'POST':
		form = UploadFileForm(request.POST, request.FILES)
		if form.is_valid() and str(os.path.splitext(request.FILES['file'].name)[1]) == '.csv':
			csv_file = request.FILES['file']
			csv_file = csv_file.read().decode('utf-8')
			csv_file = io.StringIO(csv_file)
			csv_to_models(csv_file)
			message_success = 'Información de empleados actualizada correctamente'
			return render(request, 'pdf_manager/admin_csv.html', {
				'message_success': message_success,
				'upload_csv_form': form
			})
		else:
			message = 'Documento no válido, por vafor verifique que la extensión del documento es .csv'
			return render(request, 'pdf_manager/admin_csv.html', {
				'upload_csv_form': form,
				'message': message
			})


# HR can upload PDF
def admin_pdf(request):
	form = DesprendiblesForm()
	if request.method == 'GET':
		if not request.user.is_authenticated:
			return HttpResponseRedirect(reverse("login"))
		else:
			desprendibles = Desprendibles.objects.all()
			return render(request, 'pdf_manager/admin_pdf.html', {
				'form': form,
				'desprendibles': desprendibles
			})
	
	if request.method == 'POST':
		form = DesprendiblesForm(request.POST, request.FILES)
		if form.is_valid():			
			if Desprendibles.objects.filter(quincena=form['quincena'].value(), mes=form['mes'].value(), año=form['año'].value()).exists():
				message = "El documento que intenta cargar ya existe, si desea cargarlo nuevamente por favor elimine el existente"
				desprendibles = Desprendibles.objects.all()
				return render(request, 'pdf_manager/admin_pdf.html', {
					'form': form,
					'desprendibles': desprendibles,
					'message': message
				})

			else:
				form.save()
				message_success = 'Documento cargado de forma exitosa'
				desprendibles = Desprendibles.objects.all()
				return render(request, 'pdf_manager/admin_pdf.html', {
					'form': form,
					'desprendibles': desprendibles,
					'message_success': message_success
				})


# HR can delete desprendibles
def delete_desprendible(request, pk):
	if request.method == 'POST':
		desprendible = Desprendibles.objects.get(pk = pk)
		desprendible.delete()
	return redirect('admin_pdf')


# HR can download desprendibles
def download_desprendible(request):
	if request.method == 'POST':
		file_location_in_blob = request.POST.get('pdf_download')

		file_name = file_location_in_blob.replace('media/', '')

		url = get_blob_url(file_location_in_blob)

		request = requests.get(url, stream=True)
		response = StreamingHttpResponse(streaming_content=request)

		response['Content-Disposition'] = f'attachment; filename={file_name}'

		return response


# User can download desprendibles
def download_desprendible_user(request):
	if request.method == 'POST':
		file_location_in_blob = request.POST.get('pdf_download')
		url = get_blob_url(file_location_in_blob)

		file = urllib.request.urlopen(url)

		reader = PdfFileReader(io.BytesIO(file.read()))
		for i in range(0, reader.getNumPages()):
			content = ""
			content += reader.getPage(i).extractText() + "\n"
			ResSearch = re.search(request.user.username, content)
			if ResSearch is not None:
				page = i
				break
		
		pdfWriter = PdfFileWriter()
		pdfWriter.addPage(reader.getPage(page))

		with open('desprendibles/test.pdf', 'wb') as f:
			pdfWriter.write(f)
			f.close()

		return FileResponse(open('desprendibles/test.pdf', 'rb'), content_type='application/pdf')