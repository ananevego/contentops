import asyncio

from app.collectors.apify_ocr import collect_slideshow_ocr


IMAGE_URLS = [
    "https://p16-common-sign.tiktokcdn-us.com/tos-alisg-i-photomode-sg/148a07a2bc76424c9cb1dc426d51848b~tplv-photomode-image.jpeg?dr=9616&x-expires=1789214400&x-signature=pDu55YLx4DjzuG%2BTE7ynt8N74Rk%3D&t=4d5b0474&ps=13740610&shp=81f88b70&shcp=9b759fb9&idc=useast5&ftpl=1",
        "https://p16-common-sign.tiktokcdn-us.com/tos-alisg-i-photomode-sg/bee1d9fd72cb4424a2dc570566122915~tplv-photomode-image.jpeg?dr=9616&x-expires=1789214400&x-signature=ugqsxSUeHEuMgjL0oiwLEEf0LMM%3D&t=4d5b0474&ps=13740610&shp=81f88b70&shcp=9b759fb9&idc=useast5&ftpl=1",
        "https://p16-common-sign.tiktokcdn-us.com/tos-alisg-i-photomode-sg/45496073253e47e19466c63b5d98b8c5~tplv-photomode-image.jpeg?dr=9616&x-expires=1789214400&x-signature=Eqg3PIb3HuK9FotI3KH9FDS%2Bxic%3D&t=4d5b0474&ps=13740610&shp=81f88b70&shcp=9b759fb9&idc=useast5&ftpl=1",
        "https://p16-common-sign.tiktokcdn-us.com/tos-alisg-i-photomode-sg/7b7acaf7fa0d4b88b62fc8064f47bcfd~tplv-photomode-image.jpeg?dr=9616&x-expires=1789214400&x-signature=IBMOuBWIcNNXRbq2Se7QWvK8Ios%3D&t=4d5b0474&ps=13740610&shp=81f88b70&shcp=9b759fb9&idc=useast5&ftpl=1",
        "https://p16-common-sign.tiktokcdn-us.com/tos-alisg-i-photomode-sg/19d525fbcde14f388885a9dd126f109e~tplv-photomode-image.jpeg?dr=9616&x-expires=1789214400&x-signature=gvHHsL7jfxHol3nyN%2B6WFfhM9Rg%3D&t=4d5b0474&ps=13740610&shp=81f88b70&shcp=9b759fb9&idc=useast5&ftpl=1",
        "https://p16-common-sign.tiktokcdn-us.com/tos-alisg-i-photomode-sg/e23e5ab39b0e425280e8e7ebcb3a83ef~tplv-photomode-image.jpeg?dr=9616&x-expires=1789214400&x-signature=VAYEqnA%2FFt%2BjelfolpsxYoIIE04%3D&t=4d5b0474&ps=13740610&shp=81f88b70&shcp=9b759fb9&idc=useast5&ftpl=1",
        "https://p16-common-sign.tiktokcdn-us.com/tos-alisg-i-photomode-sg/87c8ab55a0414fbf9cec9139c529a895~tplv-photomode-image.jpeg?dr=9616&x-expires=1789214400&x-signature=u3yaK6%2FqIIm94j6mtKQM8X4OZac%3D&t=4d5b0474&ps=13740610&shp=81f88b70&shcp=9b759fb9&idc=useast5&ftpl=1",
        "https://p16-common-sign.tiktokcdn-us.com/tos-alisg-i-photomode-sg/2f0198c5dc5240bf85b5eea290304779~tplv-photomode-image.jpeg?dr=9616&x-expires=1789214400&x-signature=xleKJVxCgyj26aYR%2B0BnGGaLXDE%3D&t=4d5b0474&ps=13740610&shp=81f88b70&shcp=9b759fb9&idc=useast5&ftpl=1"
]


async def main():
    results = await collect_slideshow_ocr(IMAGE_URLS)

    if not results:
        print("OCR NOT AVAILABLE")
        return

    for index, text in enumerate(results, start=1):
        print(f"\n{'=' * 60}")
        print(f"PHOTO {index}")
        print(f"{'=' * 60}\n")

        if text:
            print(text)
        else:
            print("Text not found")


if __name__ == "__main__":
    asyncio.run(main())
