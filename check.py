#!/usr/bin/python
import base64
import difflib

try:
    import urllib.request as urllib2
except ImportError:
    import urllib2
import sys
import json
import re
import socket
import subprocess
import tldextract

try:
    from urllib.parse import urlparse
except ImportError:
    from urlparse import urlparse

most_popular_tlds = ['.com', '.ru', '.net', '.org', '.de']


def get_website(url):
    command = "phantomjs --ignore-ssl-errors=true website.js \"" + url + "\" 4 website.png"
    website = json.loads(
        subprocess.check_output(command, shell=True, stderr=subprocess.STDOUT, timeout=30).decode("utf-8"))
    website['certificate'] = get_cert_info(urlparse(url)) is not None
    return website


def get_links(file, search):
    command = "phantomjs " + file + " \"" + search + "\" 10"
    try:
        return json.loads(subprocess.check_output(command, shell=True, stderr=subprocess.STDOUT, timeout=20)
                          .decode("utf-8"))
    except (ValueError, subprocess.TimeoutExpired):
        return []


def get_link(list, link):
    for item in list:
        if item['link'] == link:
            return item
    pass


def add_links(overall_link_list, links, **kwargs):
    for (index, link) in enumerate(links):
        l = get_link(overall_link_list, link)
        count = len(links) - index
        if count < kwargs.get('count', 0):
            count = kwargs.get('count', 0)
        if l:
            l["count"] += count
        else:
            overall_link_list.append({
                "link": link,
                "count": count
            })
    pass


def get_resolved_url(url):
    try:
        response = urllib2.urlopen(url, timeout=3)
        return response.geturl()
    except (urllib2.URLError, ConnectionResetError, socket.timeout):
        return None


def get_cert_info(uri):
    if uri.scheme != 'https':
        return None
    host = uri.hostname
    port = uri.port
    if port is None:
        port = 443
    command = "openssl s_client -showcerts -verify_return_error -servername " + host + " -connect " \
              + host + ":" + str(port) + " < /dev/null"
    try:
        result = subprocess.check_output(command, shell=True, stderr=subprocess.STDOUT, timeout=3).decode("utf-8")
    except subprocess.TimeoutExpired:
        return None
    verify_pattern = re.compile(r"Verify return code: (\d+ \(.*\))$", re.MULTILINE)
    verify_match = verify_pattern.search(result)
    if not verify_match:
        return None
    if verify_match.group(1) != "0 (ok)":
        return None

    cert_pattern = re.compile(r"0 s:/(.+)/CN=\S+$", re.MULTILINE)
    cert_match = cert_pattern.search(result)
    if not cert_match:
        return None
    return cert_match.group(1)


def filter_original_links(links, url):
    filtered_links = []
    uri = urlparse(url)
    ip = socket.gethostbyname(uri.hostname)
    domain = tldextract.extract(url).registered_domain
    cert_info = get_cert_info(uri)
    for item in links:
        link = get_resolved_url(item)
        if link is None:
            continue
        item_domain = tldextract.extract(link).registered_domain
        if item_domain == domain or ip == socket.gethostbyname(urlparse(link).hostname):
            continue
        if cert_info is not None:
            if cert_info == get_cert_info(urlparse(link)):
                continue
        filtered_links.append(link)
        if len(filtered_links) >= 10:
            break
    return filtered_links[:10]


def search_and_evaluate_links(keywords, url):
    search = "+".join(keyword['name'] for keyword in keywords)
    print("search for " + search)
    search_links = []
    add_links(search_links, get_links("duckduckgo.js", search))
    add_links(search_links, get_links("ixquick.js", search))
    add_links(search_links, get_links("bing.js", search))
    add_links(search_links, list(map(lambda tld: 'http://' + keywords[0]['name'] + tld, most_popular_tlds)), count=50)
    search_links.sort(key=lambda link: link["count"], reverse=True)
    return filter_original_links(list(map(lambda item: item["link"], search_links[:25])), url)


def get_responses_for_links(links):
    responses = []
    for index, url in enumerate(links):
        response = get_response(url, "screenshot" + str(index) + ".png")
        if response is not None:
            responses.append(response)
    return responses


def get_response(url, screenshotname):
    print("download " + url)
    command = "phantomjs content.js \"" + url + "\" " + screenshotname
    try:
        result = json.loads(subprocess.check_output(command, shell=True, stderr=subprocess.STDOUT, timeout=10)
                            .decode("utf-8"))
        result['url'] = url
        return result
    except (ValueError, subprocess.TimeoutExpired, subprocess.CalledProcessError):
        return None


def compare_responses_to_website(website, responses):
    for index, response in enumerate(responses):
        response['html_ratio'] = difflib.SequenceMatcher(None, website['html'], response['html']).quick_ratio()
        response['content_ratio'] = difflib.SequenceMatcher(None, website['content'], response['content']).quick_ratio()
        response['comparison'] = "compare" + str(index) + ".jpg"
        command = "nodejs compare.js " + website['screenshot'] + " " + response['screenshot'] + " " \
                  + response['comparison']
        try:
            response['screenshot_ratio'] = float(
                subprocess.check_output(command, shell=True, stderr=subprocess.STDOUT, timeout=20).decode("utf-8"))
        except (ValueError, subprocess.CalledProcessError):
            response['screenshot_ratio'] = (response['html_ratio'] + response['content_ratio']) / 2
            response['comparison'] = None
        ratio, result = calculate_result(website, response)
        response['ratio'] = ratio
        response['result'] = result
    pass


def calculate_result(website, response):
    ratio_subtract = 0
    if website['password_field'] and not website['certificate']:
        ratio_subtract = 0.05

    suspicious_min = 0.82 - ratio_subtract
    suspicious_min_with_other = 0.77 - ratio_subtract
    suspicious_screenshot_min = 0.91 - ratio_subtract
    suspicious_html_min = 0.93 - ratio_subtract
    suspicious_content_min = 0.95 - ratio_subtract

    malicious_min = 0.9 - ratio_subtract
    malicious_min_with_other = 0.85 - ratio_subtract
    malicious_screenshot_min = 0.96 - ratio_subtract
    malicious_html_min = 0.97 - ratio_subtract
    malicious_content_min = 0.98 - ratio_subtract

    ratio = (response['screenshot_ratio'] * 2 + response['html_ratio'] + response['content_ratio']) / 4
    result = 'CLEAN'
    if ratio > suspicious_min or (ratio > suspicious_min_with_other
                                  and (response['screenshot_ratio'] > suspicious_screenshot_min
                                       or response['html_ratio'] > suspicious_html_min
                                       or response["content_ratio"] > suspicious_content_min)):
        result = 'SUSPICIOUS'
    if ratio > malicious_min or (ratio > malicious_min_with_other
                                 and (response['screenshot_ratio'] > malicious_screenshot_min
                                      or response['html_ratio'] > malicious_html_min
                                      or response["content_ratio"] > malicious_content_min)):
        result = 'MALICIOUS'
    return ratio, result


def format_result(website, responses):
    matches = []
    result = "CLEAN"
    for response in responses:
        if response['result'] != 'CLEAN':
            if response['result'] == 'MALICIOUS':
                result = 'MALICIOUS'
            elif result == 'CLEAN':
                result = 'SUSPICIOUS'
            comparison = None
            if response['comparison'] is not None:
                with open(response['comparison'], "rb") as image_file:
                    comparison = 'data:image/jpg;base64,' + base64.b64encode(image_file.read()).decode("utf-8")
            matches.append({
                'url': response['url'],
                'result': response['result'],
                'ratio': response['ratio'],
                'html_ratio': response['html_ratio'],
                'content_ratio': response['content_ratio'],
                'screenshot_ratio': response['screenshot_ratio'],
                'comparison': comparison
            })

    return {
        "result": result,
        "info": {
            "keywords": list(map(lambda keyword: keyword['name'], website['keywords'])),
            "matches": matches
        }
    }


if __name__ == "__main__":
    if len(sys.argv) == 3:
        prefix = sys.argv[1]
        url = sys.argv[2]
        website = get_website(url)
        if len(website['keywords']) > 0:
            links = search_and_evaluate_links(website['keywords'], url)
            print("found " + str(len(links)) + " possible websites that could match")

            responses = get_responses_for_links(links)
            print("downloaded " + str(len(responses)) + " of them")
            compare_responses_to_website(website, responses)
            print('{}: {}'.format(prefix, json.dumps(format_result(website, responses))))
        else:
            print("no keywords found!")
    else:
        print("prefix or url missing")
