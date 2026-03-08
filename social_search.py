import os
import requests
import random
from typing import List, Dict, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from bs4 import BeautifulSoup

try:
    import tweepy
except ImportError:
    tweepy = None

try:
    import praw
except ImportError:
    praw = None

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
]


class SocialSearch:
    def __init__(self, twitter_token: Optional[str] = None, reddit_client: Optional[object] = None):
        self.twitter_token = twitter_token
        self.reddit_client = reddit_client
        
        if tweepy and twitter_token:
            try:
                self.twitter_client = tweepy.Client(bearer_token=twitter_token)
            except Exception as e:
                print(f"Twitter client init error: {e}")
                self.twitter_client = None
        else:
            self.twitter_client = None
    
    def search_twitter(self, query: str, max_results: int = 10) -> List[Dict]:
        results = []
        
        if not self.twitter_client:
            return results
        
        try:
            tweets = self.twitter_client.search_recent_tweets(
                query=query,
                max_results=min(max_results, 100),
                tweet_fields=["created_at", "author_id", "public_metrics"]
            )
            
            if tweets.data:
                for tweet in tweets.data:
                    results.append({
                        "title": tweet.text[:200],
                        "content": tweet.text,
                        "author_id": str(tweet.author_id) if tweet.author_id else "",
                        "created_at": str(tweet.created_at) if tweet.created_at else "",
                        "likes": tweet.public_metrics.get("like_count", 0) if tweet.public_metrics else 0,
                        "retweets": tweet.public_metrics.get("retweet_count", 0) if tweet.public_metrics else 0,
                        "source": "Twitter/X"
                    })
        except Exception as e:
            print(f"Twitter search error: {e}")
        
        return results
    
    def search_reddit(self, query: str, max_results: int = 10) -> List[Dict]:
        results = []
        
        if not self.reddit_client:
            return results
        
        try:
            subreddits = ["all", "technology", "science", "news", "worldnews"]
            
            for subreddit_name in subreddits[:2]:
                try:
                    subreddit = self.reddit_client.subreddit(subreddit_name)
                    posts = subreddit.search(query, limit=max_results)
                    
                    for post in posts:
                        results.append({
                            "title": post.title,
                            "content": post.selftext[:500] if post.selftext else "",
                            "author": str(post.author) if post.author else "",
                            "score": post.score,
                            "num_comments": post.num_comments,
                            "created_utc": str(post.created_utc),
                            "url": post.url,
                            "source": f"Reddit r/{subreddit_name}"
                        })
                except Exception as e:
                    print(f"Reddit search error in {subreddit_name}: {e}")
        except Exception as e:
            print(f"Reddit search error: {e}")
        
        return results
    
    def search_reddit_public(self, query: str, max_results: int = 10) -> List[Dict]:
        results = []
        
        try:
            url = f"https://www.reddit.com/search.json?q={requests.utils.quote(query)}&limit={max_results}&sort=relevance"
            headers = {
                "User-Agent": random.choice(USER_AGENTS),
                "Accept": "application/json"
            }
            response = requests.get(url, headers=headers, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                children = data.get("data", {}).get("children", [])
                
                for child in children:
                    post = child.get("data", {})
                    if post.get("is_video") or post.get("nsfw"):
                        continue
                    results.append({
                        "title": post.get("title", ""),
                        "content": post.get("selftext", "")[:500],
                        "author": post.get("author", ""),
                        "score": post.get("score", 0),
                        "num_comments": post.get("num_comments", 0),
                        "created_utc": post.get("created_utc", ""),
                        "url": f"https://reddit.com{post.get('permalink', '')}",
                        "source": "Reddit"
                    })
        except Exception as e:
            print(f"Reddit public search error: {e}")
        
        return results
    
    def search_hackernews(self, query: str, max_results: int = 10) -> List[Dict]:
        results = []
        
        try:
            url = f"https://hn.algolia.com/api/v1/search"
            params = {"query": query, "tags": "story", "hitsPerPage": max_results}
            headers = {"User-Agent": random.choice(USER_AGENTS)}
            
            response = requests.get(url, params=params, headers=headers, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                hits = data.get("hits", [])
                
                for hit in hits:
                    results.append({
                        "title": hit.get("title", ""),
                        "content": hit.get("story_text", "")[:500] if hit.get("story_text") else "",
                        "author": hit.get("author", ""),
                        "score": hit.get("points", 0),
                        "num_comments": hit.get("num_comments", 0),
                        "created_utc": hit.get("created_at", ""),
                        "url": hit.get("url", f"https://news.ycombinator.com/item?id={hit.get('objectID')}"),
                        "source": "Hacker News"
                    })
        except Exception as e:
            print(f"Hacker News search error: {e}")
        
        return results
    
    def search_stackoverflow(self, query: str, max_results: int = 10) -> List[Dict]:
        results = []
        
        try:
            url = "https://api.stackexchange.com/2.3/search/advanced"
            params = {
                "order": "desc",
                "sort": "relevance",
                "q": query,
                "site": "stackoverflow",
                "pagesize": max_results
            }
            headers = {"User-Agent": random.choice(USER_AGENTS)}
            
            response = requests.get(url, params=params, headers=headers, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                items = data.get("items", [])
                
                for item in items:
                    results.append({
                        "title": item.get("title", ""),
                        "content": item.get("body_markdown", "")[:500] if item.get("body_markdown") else "",
                        "author": item.get("owner", {}).get("display_name", ""),
                        "score": item.get("score", 0),
                        "num_comments": item.get("answer_count", 0),
                        "created_utc": item.get("creation_date", ""),
                        "url": item.get("link", ""),
                        "source": "Stack Overflow"
                    })
        except Exception as e:
            print(f"Stack Overflow search error: {e}")
        
        return results
    
    def search_zhihu(self, query: str, max_results: int = 10) -> List[Dict]:
        results = []
        
        try:
            url = f"https://www.zhihu.com/api/v4/search_v3"
            params = {
                "q": query,
                "type": "topic",
                "limit": max_results,
                "offset": 0
            }
            headers = {
                "User-Agent": random.choice(USER_AGENTS),
                "Referer": "https://www.zhihu.com"
            }
            
            response = requests.get(url, params=params, headers=headers, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                items = data.get("data", [])
                
                for item in items:
                    results.append({
                        "title": item.get("highlight", {}).get("title", item.get("name", "")),
                        "content": item.get("excerpt", "")[:500] if item.get("excerpt") else "",
                        "author": "",
                        "score": item.get("follower_count", 0),
                        "num_comments": item.get("discussion_count", 0),
                        "created_utc": "",
                        "url": f"https://www.zhihu.com/topic/{item.get('id', '')}",
                        "source": "知乎"
                    })
        except Exception as e:
            print(f"Zhihu search error: {e}")
        
        return results
    
    def search_weibo(self, query: str, max_results: int = 10) -> List[Dict]:
        results = []
        
        try:
            url = "https://m.weibo.cn/api/container/getIndex"
            params = {
                "containerid": f"100103type=1&q={requests.utils.quote(query)}",
                "page": 1
            }
            headers = {
                "User-Agent": random.choice(USER_AGENTS),
                "Referer": "https://m.weibo.cn"
            }
            
            response = requests.get(url, params=params, headers=headers, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                cards = data.get("data", {}).get("cards", [])
                
                for card in cards:
                    if card.get("card_type") == 9:
                        mblog = card.get("mblog", {})
                        results.append({
                            "title": mblog.get("text", "")[:200],
                            "content": mblog.get("text", ""),
                            "author": mblog.get("user", {}).get("screen_name", ""),
                            "score": mblog.get("attitudes_count", 0),
                            "num_comments": mblog.get("comments_count", 0),
                            "created_utc": mblog.get("created_at", ""),
                            "url": f"https://weibo.com/detail/{mblog.get('id', '')}",
                            "source": "微博"
                        })
        except Exception as e:
            print(f"Weibo search error: {e}")
        
        return results
    
    def search(self, query: str, max_results: int = 10) -> List[Dict]:
        all_results = []
        
        with ThreadPoolExecutor(max_workers=6) as executor:
            futures = []
            
            if self.twitter_client:
                futures.append(executor.submit(self.search_twitter, query, max_results))
            
            if self.reddit_client:
                futures.append(executor.submit(self.search_reddit, query, max_results))
            else:
                futures.append(executor.submit(self.search_reddit_public, query, max_results))
            
            futures.append(executor.submit(self.search_hackernews, query, max_results))
            futures.append(executor.submit(self.search_stackoverflow, query, max_results))
            futures.append(executor.submit(self.search_zhihu, query, max_results))
            futures.append(executor.submit(self.search_weibo, query, max_results))
            
            for future in as_completed(futures):
                try:
                    results = future.result()
                    if results:
                        all_results.extend(results)
                except Exception as e:
                    print(f"Search error: {e}")
        
        all_results.sort(key=lambda x: x.get("score", 0) + x.get("likes", 0), reverse=True)
        return all_results[:max_results * 3]


def get_social_results(query: str, max_results: int = 10, twitter_token: Optional[str] = None) -> List[Dict]:
    searcher = SocialSearch(twitter_token=twitter_token)
    return searcher.search(query, max_results)
