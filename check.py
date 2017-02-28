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


def get_website(url):
    command = "phantomjs --ignore-ssl-errors=true website.js \"" + url + "\" 3 website.jpg"
    return json.loads(subprocess.check_output(command, shell=True, stderr=subprocess.PIPE, timeout=30)
                      .decode("utf-8"))


def get_links(file, search):
    command = "phantomjs " + file + " \"" + search + "\" 10"
    try:
        return json.loads(subprocess.check_output(command, shell=True, stderr=subprocess.PIPE, timeout=20)
                          .decode("utf-8"))
    except (ValueError, subprocess.TimeoutExpired):
        return []


def get_link(list, link):
    for item in list:
        if item['link'] == link:
            return item
    pass


def add_links(overall_link_list, links):
    for (index, link) in enumerate(links):
        l = get_link(overall_link_list, link)
        if l:
            l["count"] += len(links) - index
        else:
            overall_link_list.append({
                "link": link,
                "count": len(links) - index
            })
    pass


def get_resolved_url(url):
    try:
        response = urllib2.urlopen(url)
        return response.geturl()
    except urllib2.URLError:
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
        result = subprocess.check_output(command, shell=True, stderr=subprocess.PIPE, timeout=3).decode("utf-8")
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
    uri = urlparse(url)
    ip = socket.gethostbyname(uri.hostname)
    domain = tldextract.extract(url).registered_domain
    cert_info = get_cert_info(uri)
    for item in links[:]:
        link = get_resolved_url(item['link'])
        if link is None:
            links.remove(item)
            continue
        item_domain = tldextract.extract(link).registered_domain
        if item_domain == domain or ip == socket.gethostbyname(urlparse(link).hostname):
            links.remove(item)
            continue
        if cert_info is not None:
            if cert_info == get_cert_info(urlparse(link)):
                links.remove(item)
    return links[:7]


def get_and_evaluate_links(search, url):
    links = []
    add_links(links, get_links("duckduckgo.js", search))
    add_links(links, get_links("ixquick.js", search))
    add_links(links, get_links("bing.js", search))
    links.sort(key=lambda link: link["count"], reverse=True)
    return list(map(lambda item: item["link"], filter_original_links(links[:25], url)))


def get_responses_for_links(links):
    responses = []
    for index, url in enumerate(links):
        response = get_response(url, "screenshot" + str(index) + ".jpg")
        if response is not None:
            responses.append(response)
    return responses


def get_response(url, screenshotname):
    print("download " + url)
    command = "phantomjs content.js \"" + url + "\" " + screenshotname
    try:
        result = json.loads(subprocess.check_output(command, shell=True, stderr=subprocess.PIPE, timeout=10)
                            .decode("utf-8"))
        result['url'] = url
        return result
    except (ValueError, subprocess.TimeoutExpired):
        return None


def compare_responses_to_website(website, responses):
    for index, response in enumerate(responses):
        response['html_ratio'] = difflib.SequenceMatcher(None, website['html'], response['html']).quick_ratio()
        response['content_ratio'] = difflib.SequenceMatcher(None, website['content'], response['content']).quick_ratio()
        response['comparison'] = "compare" + str(index) + ".jpg"
        command = "nodejs compare.js " + website['screenshot'] + " " + response['screenshot'] + " " \
                  + response['comparison']
        try:
            response['screenshot_ratio'] = float(json.loads(
                subprocess.check_output(command, shell=True,
                                        stderr=subprocess.PIPE, timeout=20).decode("utf-8")))
        except ValueError:
            response['screenshot_ratio'] = (response['html_ratio'] + response['content_ratio']) / 2
        ratio, result = calculate_result(response)
        response['ratio'] = ratio
        response['result'] = result
    pass


def calculate_result(response):
    ratio = (response['screenshot_ratio'] * 2 + response['html_ratio'] + response['content_ratio']) / 4
    result = 'CLEAN'
    if ratio > 0.85 or (ratio > 0.78 and (response['screenshot_ratio'] > 0.9
                                          or response['html_ratio'] > 0.92 or response["content_ratio"] > 0.95)):
        result = 'SUSPICIOUS'
    if ratio > 0.95 or (ratio > 0.83 and (response['screenshot_ratio'] > 0.96
                                          or response['html_ratio'] > 0.97 or response["content_ratio"] > 0.98)):
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
            comparison = "data:image/jpg;base64," + base64.b64encode(open(response['comparison']).read())
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
        search = "+".join(keyword['name'] for keyword in website['keywords'])
        if len(search) > 0:
            print("search for " + search)
            links = get_and_evaluate_links(search, url)
            print("found " + str(len(links)) + " possible websites that could match")

            responses = get_responses_for_links(links)
            print("downloaded " + str(len(responses)) + " of them")
            compare_responses_to_website(website, responses)
            print('{}: {}'.format(prefix, json.dumps(format_result(website, responses))))
        else:
            print("no keywords found!")
    else:
        print("prefix or url missing")
