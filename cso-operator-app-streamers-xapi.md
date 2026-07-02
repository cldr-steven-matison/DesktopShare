**Here are the official X API (v2) docs for video uploads, including the chunked upload process (which you're likely already using), metadata, and subtitles.**

### 1. Chunked Video Upload (Core Process)
Your current uploads probably use this workflow. Videos must use chunked upload for files over a certain size.

**Official guide:**  
[Chunked Media Upload – X API v2](https://docs.x.com/x-api/media/quickstart/media-upload-chunked)

**Key endpoint:** `POST https://api.x.com/2/media/upload`

**Main steps (with `media_category` for videos):**
- **INIT**: Start the session and get a `media_id`.
  - Parameters: `command=INIT`, `media_type=video/mp4`, `total_bytes=...`, `media_category=tweet_video` (or `amplify_video` for longer/higher-quality videos).
- **APPEND**: Upload file chunks (repeat for each segment).
  - Parameters: `command=APPEND`, `media_id=...`, `segment_index=0,1,2,...`, `media=@chunk_file`.
- **FINALIZE**: Complete the upload.
  - Parameters: `command=FINALIZE`, `media_id=...`.
- **STATUS** (if needed): Poll until `processing_info.state=succeeded`.
  - `GET https://api.x.com/2/media/upload?command=STATUS&media_id=...`

**Authentication**: OAuth 2.0 User Token (Bearer token) with `media.write` scope (and usually `tweet.write` to post later). Use user context, not app-only.

After successful upload + processing, attach the `media_id` (or `media_key`) when creating a Post via `POST /2/posts` (or `/2/tweets` in some contexts).

**Example flow** (cURL snippets are in the official guide linked above). Many libraries (e.g., tweepy, twitter-api-v2) now support the v2 media upload.

**Note on "untitled" videos**: The video media itself often appears as "Untitled" in the Media Library when uploaded purely via API. This is a known limitation—title/description settings for the video asset (visible in Media Studio) are primarily a UI feature and are **not directly supported** in the public X API v2 metadata endpoint for programmatic setting. Third-party tools (e.g., Ayrshare) sometimes expose `videoTitle`/`videoDescription` fields that map to Media Studio, but these are not part of the official X API.

### 2. Adding Metadata to Uploaded Media
**New endpoint (announced ~early 2025):**  
[Create Media Metadata – POST /2/media/metadata](https://docs.x.com/x-api/media/create-media-metadata) (or `/2/media/metadata`)

This lets you add additional metadata to a previously uploaded media file (after INIT/FINALIZE).

**Supported metadata fields** (from docs):
- `allow_download_status`
- `audience_policy` (creator_subscriptions, x_subscriptions)
- `geo_restrictions`
- `sensitive_media_warning`
- Others like `alt_text` (mainly for images), preview settings, etc.

**Request example structure**:
```json
{
  "id": "your_media_id_here",
  "metadata": {
    "allow_download_status": { "allow_download": true },
    "sensitive_media_warning": { "adult_content": false, ... }
    // Add other supported fields as needed
  }
}
```

**Content-Type**: `application/json`  
**Auth**: Bearer user token.

**Important**: Official docs for this endpoint do **not** include fields for video `title`, `description`, or `call to action`. These appear to be Media Studio-only settings (editable in the UI after upload: Settings tab → Title, Description, Category, Call-to-action, etc.). Changes to title/description/CTA in Media Studio generally apply to new posts using that media.

If you're seeing "untitled," this is likely why—there's no public API parameter to set the video asset title/description directly.

### 3. Adding Subtitles (.srt file)
**New endpoint:**  
[Create Media Subtitles – POST /2/media/subtitles](https://docs.x.com/x-api/media/create-media-subtitles) (and delete endpoint available).

**Process** (based on v2 announcement + historical v1.1 behavior, which the v2 endpoints mirror):
1. **Upload the .srt file first** as a media asset (using the same chunked `POST /2/media/upload` endpoint).
   - Typical parameters for SRT: `command=INIT`, `media_type=text/plain;charset=UTF-8`, `media_category=SUBTITLES` (or similar), `total_bytes=...`.
   - Then APPEND the file content, then FINALIZE. This gives you a separate `media_id` for the subtitle file.
2. **Associate it with your video** using the subtitles endpoint:
   ```json
   {
     "id": "your_video_media_id",
     "media_category": "TweetVideo",   // or "AmplifyVideo"
     "subtitles": {
       "id": "your_srt_media_id",      // from the SRT upload above
       "language_code": "en",
       "display_name": "English"
     }
   }
   ```

You can support multiple languages by repeating the association process or structuring the `subtitles` array/object accordingly (check exact schema in docs).

**Official subtitles docs link above** for full request/response format. The SRT file must be valid SubRip format. Processing happens after association.

**Note**: Subtitles are associated with the video media and can appear on posts using that video (viewers need closed captions enabled).

### Additional Tips for Your Setup
- **Migrate fully to v2** if you're still on the old `upload.twitter.com/1.1/media/upload.json` — v1.1 media upload was deprecated around early 2025.
- **Post creation**: After getting the `media_id`, create the Post with text (your description/CTA can go here) + `media.media_ids`.
- **Scopes & Auth**: Ensure your app has `media.write` + `tweet.write` (or equivalent) and you're using a user access token.
- **Media Studio alternative**: For full title, description, call-to-action, category, etc., upload via API then edit in Media Studio (help.x.com has UI instructions). Some settings (e.g., subtitles, geo) can be updated retroactively for existing media.
- **Limits & Best Practices**: Check the chunked guide for file size/duration limits, chunk sizes, and processing wait times. Videos often need the STATUS poll.

**Direct links to bookmark**:
- Chunked upload: https://docs.x.com/x-api/media/quickstart/media-upload-chunked
- Media metadata: https://docs.x.com/x-api/media/create-media-metadata
- Media subtitles: https://docs.x.com/x-api/media/create-media-subtitles

If your current code is close but missing the metadata/subtitles steps, add the post-upload calls to `/2/media/metadata` and the subtitles workflow.

For the most up-to-date examples or if you hit specific errors (e.g., auth scopes, exact SRT upload params in v2), check the X Developer Community or the docs portal directly. Let me know your current code snippet or error if you need help debugging the integration!