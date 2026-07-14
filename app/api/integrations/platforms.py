# app/integrations/platforms.py
import httpx
import time
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

class PlatformAPIError(Exception):
    """Custom exception for platform API errors (e.g., 429, 613, 401)"""
    pass

class FacebookAPI:
    """
    Handles Facebook Page posts and Instagram Business account posts.
    (Chapters 6.1 & 6.2) - Both use the Meta Graph API.
    """
    BASE_URL = "https://graph.facebook.com/v19.0"

    @staticmethod
    def fetch_posts(page_id: str, access_token: str, days: int = 7) -> List[Dict[str, Any]]:
        """
        Fetches Facebook Page posts with summary engagement metrics.
        Implements Chapter 9.5 (Field Selection) to reduce BUC point cost.
        """
        since_timestamp = int(time.time()) - (days * 86400)
        url = f"{FacebookAPI.BASE_URL}/{page_id}/posts"
        
        params = {
            "fields": "id,message,created_time,permalink_url,full_picture,"
                      "reactions.summary(total_count),"
                      "comments.summary(total_count),"
                      "shares",
            "since": since_timestamp,
            "limit": 100, # Chapter 6.4: Max 100 per page
            "access_token": access_token
        }

        all_posts = []
        next_url = url
        next_params = params

        # Handle cursor-based pagination (Chapter 6.4)
        while next_url:
            response = httpx.get(next_url, params=next_params, timeout=10.0)
            if response.status_code in (429, 613):
                raise PlatformAPIError(f"FB Rate limit hit for page {page_id}")
            response.raise_for_status()
            
            data = response.json()
            all_posts.extend(data.get("data", []))
            
            paging = data.get("paging", {})
            next_url = paging.get("next")
            next_params = None # 'next' URL already contains all params

        return FacebookAPI._parse_fb_posts(all_posts)

    @staticmethod
    def fetch_instagram_posts(ig_user_id: str, access_token: str, days: int = 7) -> List[Dict[str, Any]]:
        """
        Fetches Instagram Business account media.
        Uses the FB Page access token (Chapter 6.2).
        """
        since_timestamp = int(time.time()) - (days * 86400)
        url = f"{FacebookAPI.BASE_URL}/{ig_user_id}/media"
        
        params = {
            "fields": "id,caption,timestamp,media_url,thumbnail_url,permalink,"
                      "like_count,comments_count,media_type",
            "since": since_timestamp,
            "limit": 100,
            "access_token": access_token
        }

        all_posts = []
        next_url = url
        next_params = params

        while next_url:
            response = httpx.get(next_url, params=next_params, timeout=10.0)
            if response.status_code in (429, 613):
                raise PlatformAPIError(f"IG Rate limit hit for user {ig_user_id}")
            response.raise_for_status()
            
            data = response.json()
            all_posts.extend(data.get("data", []))
            
            paging = data.get("paging", {})
            next_url = paging.get("next")
            next_params = None

        return FacebookAPI._parse_ig_posts(all_posts)

    @staticmethod
    def _parse_fb_posts(raw_posts: List[Dict]) -> List[Dict[str, Any]]:
        """Maps raw FB API response to our internal DB schema format."""
        parsed = []
        for p in raw_posts:
            parsed.append({
                "platform_post_id": p.get("id"),
                "caption": p.get("message", ""), # FB uses 'message', not 'caption'
                "permalink_url": p.get("permalink_url", ""),
                "created_at": datetime.fromisoformat(p["created_time"].replace("Z", "+00:00")),
                "likes": p.get("reactions", {}).get("summary", {}).get("total_count", 0),
                "comments": p.get("comments", {}).get("summary", {}).get("total_count", 0),
                "shares": p.get("shares", {}).get("count", 0),
                "raw_response": p
            })
        return parsed

    @staticmethod
    def _parse_ig_posts(raw_posts: List[Dict]) -> List[Dict[str, Any]]:
        """Maps raw IG API response to our internal DB schema format."""
        parsed = []
        for p in raw_posts:
            parsed.append({
                "platform_post_id": p.get("id"),
                "caption": p.get("caption", ""),
                "permalink_url": p.get("permalink", ""),
                "created_at": datetime.fromisoformat(p["timestamp"].replace("Z", "+00:00")),
                "likes": p.get("like_count", 0),
                "comments": p.get("comments_count", 0),
                "shares": 0, # Chapter 6.2: IG API does not expose share counts
                "raw_response": p
            })
        return parsed


class LinkedInAPI:
    """
    Handles LinkedIn Organization posts.
    (Chapter 6.3) - Requires a two-step process: fetch posts, then fetch social actions.
    """
    BASE_URL = "https://api.linkedin.com/v2"

    @staticmethod
    def fetch_posts(org_urn: str, access_token: str, days: int = 7) -> List[Dict[str, Any]]:
        """
        Fetches LinkedIn org posts and their engagement metrics.
        org_urn format: 'urn:li:organization:12345'
        """
        since_date = datetime.utcnow() - timedelta(days=days)
        headers = {
            "Authorization": f"Bearer {access_token}",
            "X-Restli-Protocol-Version": "2.0.0"
        }

        # Step 1: Fetch Posts (Chapter 6.3)
        # Using offset-based pagination
        all_posts = []
        start = 0
        count = 50 # Chapter 6.4: Max 50 per page for LinkedIn
        
        while True:
            url = f"{LinkedInAPI.BASE_URL}/ugcPosts"
            params = {
                "q": "authors",
                "authors": org_urn,
                "projection": "(elements*(id,specificContent*(com.linkedin.ugcpost.*"
                              "(shareCommentary(text),shareMedia*(media~(*)),firstPublishedAt)),"
                              "lifecycleContext:(lastModified)))",
                "count": count,
                "start": start
            }
            
            response = httpx.get(url, headers=headers, params=params, timeout=10.0)
            if response.status_code == 429:
                raise PlatformAPIError(f"LI Rate limit hit for org {org_urn}")
            response.raise_for_status()
            
            data = response.json()
            elements = data.get("elements", [])
            
            if not elements:
                break
                
            all_posts.extend(elements)
            start += count

        # Step 2: Fetch Social Actions (Likes, Comments, Shares) for each post
        parsed_posts = []
        for post in all_posts:
            post_urn = post.get("id")
            published_ts = post.get("specificContent", {}) \
                            .get("com.linkedin.ugcpost", {}) \
                            .get("firstPublishedAt")
            
            if not published_ts:
                continue
                
            created_at = datetime.fromtimestamp(published_ts / 1000.0, tz=None) # LI returns ms
                
            # Skip if post is older than our window
            if created_at < since_date:
                continue

            # Fetch social actions for this specific post URN
            # In production, Chapter 6.3 recommends batching these concurrently with asyncio
            actions_url = f"{LinkedInAPI.BASE_URL}/socialActions/{post_urn}"
            actions_resp = httpx.get(actions_url, headers=headers, timeout=10.0)
            
            likes, comments, shares = 0, 0, 0
            if actions_resp.status_code == 200:
                actions_data = actions_resp.json()
                
                # Chapter 6.3: total likes = paging.total when filtering by Likes only.
                # The API returns a combined list, so we count by $type
                elements = actions_data.get("elements", [])
                for action in elements:
                    action_type = action.get("$type")
                    if "Like" in action_type: likes += 1
                    elif "Comment" in action_type: comments += 1
                    elif "Reshare" in action_type: shares += 1

            caption_text = post.get("specificContent", {}) \
                                .get("com.linkedin.ugcpost", {}) \
                                .get("shareCommentary", {}) \
                                .get("text", "")

            parsed_posts.append({
                "platform_post_id": post_urn,
                "caption": caption_text,
                "permalink_url": f"https://www.linkedin.com/feed/update/{post_urn.replace('urn:li:ugcPost:', '')}",
                "created_at": created_at,
                "likes": likes,
                "comments": comments,
                "shares": shares,
                "raw_response": post
            })

        return parsed_posts