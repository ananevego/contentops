from app.normalizers.tiktok import normalize_tiktok



if tiktok_videos:
    first_video = tiktok_videos[0]

    content = normalize_tiktok(first_video)

    print(content)
