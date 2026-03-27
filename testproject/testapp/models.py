from wagtail import blocks
from wagtail.admin.panels import FieldPanel
from wagtail.fields import StreamField
from wagtail.models import Page

from .blocks import (
    BadgeBlock,
    ButtonBlock,
    ContainerBlock,
    CTABannerBlock,
    EnhancedHeroSectionBlock,
    FAQSectionBlock,
    FeatureGridBlock,
    FooterSectionBlock,
    HeroSectionBlock,
    LogoCloudBlock,
    PricingSectionBlock,
    RichTextSectionBlock,
    StatsSectionBlock,
    TagListBlock,
    TestimonialSectionBlock,
    TextWithImageBlock,
)


class TestPage(Page):
    """Page type used only in the test suite.

    The StreamField covers a wide variety of block shapes so block inspection
    can be verified against realistic content patterns:

    - Primitive blocks  : text (CharBlock), rich_text (RichTextBlock)
    - Custom structs     : hero (HeroSectionBlock)
    - Library blocks     : (none in current StreamField; extend body as needed)
    """

    body = StreamField(
        [
            ("text", blocks.CharBlock()),
            ("rich_text", blocks.RichTextBlock()),
            # Original custom content blocks
            ("hero", HeroSectionBlock()),
            # New CMS blocks migrated from React
            ("badge", BadgeBlock()),
            ("cms_button", ButtonBlock()),
            ("enhanced_hero", EnhancedHeroSectionBlock()),
            ("feature_grid", FeatureGridBlock()),
            ("pricing_section", PricingSectionBlock()),
            ("stats_section", StatsSectionBlock()),
            ("testimonial_section", TestimonialSectionBlock()),
            ("text_with_image", TextWithImageBlock()),
            ("logo_cloud", LogoCloudBlock()),
            ("container", ContainerBlock()),
            ("cta_banner", CTABannerBlock()),
            ("faq_section", FAQSectionBlock()),
            ("footer_section", FooterSectionBlock()),
            ("rich_text_section", RichTextSectionBlock()),
            ("tag_list", TagListBlock()),
        ],
        use_json_field=True,
        blank=True,
    )

    content_panels = Page.content_panels + [
        FieldPanel("body"),
    ]
