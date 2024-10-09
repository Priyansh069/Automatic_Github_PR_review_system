import requests
from django.shortcuts import render, redirect
from django.conf import settings
from django.http import JsonResponse
from .models import GithubToken
import json
from django.views.decorators.csrf import csrf_exempt
import time

# This renders the HTML template with a button
def github_connect(request):
    return render(request, 'review/connect.html')

# This view handles the actual OAuth redirect to GitHub
def github_redirect(request):
    client_id = settings.GITHUB_CLIENT_ID
    redirect_uri = 'http://localhost:8000/oauth/callback/'
    github_url = f"https://github.com/login/oauth/authorize?client_id={client_id}&redirect_uri={redirect_uri}"
    return redirect(github_url)

# 2. OAuth Callback
def github_callback(request):
    code = request.GET.get('code')
    client_id = settings.GITHUB_CLIENT_ID
    client_secret = settings.GITHUB_CLIENT_SECRET
    token_url = 'https://github.com/login/oauth/access_token'

    # Exchange code for access token
    response = requests.post(token_url, headers={'Accept': 'application/json'}, data={
        'client_id': client_id,
        'client_secret': client_secret,
        'code': code
    })

    token_data = response.json()
    access_token = token_data.get('access_token')

    # Save token in the database
    GithubToken.objects.create(token=access_token)

    return render(request, 'review/success.html', {'token': access_token})


# 3. GitHub Webhook Handler
@csrf_exempt
def github_webhook(request):
    if request.method == 'POST':
        event = request.META.get('HTTP_X_GITHUB_EVENT')
        payload = request.body.decode('utf-8')

        if event == 'pull_request':
            process_pull_request(payload)

        return JsonResponse({'status': 'success'})

    return JsonResponse({'status': 'failure'}, status=400)


# 4. Process Pull Request Data
def process_pull_request(payload):
    payload = json.loads(payload)
    pr_data = payload.get('pull_request', {})
    pr_title = pr_data.get('title')
    pr_body = pr_data.get('body')

    # Call Hugging Face API for PR review
    review = call_huggingface_for_review(pr_title, pr_body)

    # Post review comment on GitHub
    post_review_comment(pr_data, review)


import requests
from django.conf import settings

def call_huggingface_for_review(pr_title, pr_body):
    API_URL = "https://api-inference.huggingface.co/models/openai-community/gpt2"
    headers = {"Authorization": f"Bearer {settings.HUGGINGFACE_API_KEY}"}

    if not pr_body or pr_body.lower() == 'none':
        pr_body = "The pull request does not contain a description. Please review based on the title."

    prompt = f"""
    You are an AI code reviewer. Please analyze the following pull request carefully:

    Title: {pr_title}
    Description: {pr_body}

    Based on the information provided, suggest potential improvements, highlight any issues, and provide feedback about the changes made in the pull request. Focus on code quality, clarity, potential edge cases, and best practices.

    Respond with a concise and focused review.
    """

    payload = {
        "inputs": prompt,
        "max_length": 300  # Adjust the length as needed
    }

    try:
        response = requests.post(API_URL, headers=headers, json=payload)
        response.raise_for_status()

        # Get the generated text from the response
        generated_text = response.json()[0]["generated_text"]

        # Remove the prompt part from the generated text
        review_text = generated_text.replace(prompt.strip(), "").strip()

        # Optionally clean up any additional text that may be irrelevant
        review_text = clean_review_output(review_text)

        return review_text if review_text else "No review provided."

    except requests.exceptions.HTTPError as e:
        print(f"HTTP error: {str(e)}")
        return f"Error: Unable to process the request - {str(e)}"

    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        return f"Error: {str(e)}"

def clean_review_output(response_text):
    # Example cleaning logic to remove irrelevant text
    filtered_text = response_text.split("See also:")[0]
    return filtered_text.strip()



# 6. Post Review as a Comment on GitHub
def post_review_comment(pr_data, review):
    pr_number = pr_data.get('number')
    repo_full_name = pr_data.get('base', {}).get('repo', {}).get('full_name')

    # Get token from database
    token = GithubToken.objects.first().token
    api_url = f"https://api.github.com/repos/{repo_full_name}/issues/{pr_number}/comments"

    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }

    data = {
        "body": review
    }

    response = requests.post(api_url, headers=headers, json=data)
    return response.status_code
