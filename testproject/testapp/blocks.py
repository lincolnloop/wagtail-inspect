"""Custom StreamField blocks for the testapp.

These blocks exercise block inspection across a variety of block shapes —
StructBlocks with multiple field types, ChoiceBlocks, URLBlocks, and
RichTextBlocks — so that the inspection tooling can be verified against
realistic content patterns.
"""

from wagtail import blocks
from wagtail.images.blocks import ImageChooserBlock


class ButtonBlock(blocks.StructBlock):
    """Reusable CTA link with label, URL, visual variant, and size.
    Shared by hero lists, pricing cards, banners, and the standalone stream block.
    """

    label = blocks.CharBlock(max_length=100, default="Get Started")
    href = blocks.URLBlock(default="https://example.com")
    variant = blocks.ChoiceBlock(
        choices=[
            ("primary", "Primary"),
            ("secondary", "Secondary"),
            ("outline", "Outline"),
            ("ghost", "Ghost"),
        ],
        default="primary",
    )
    size = blocks.ChoiceBlock(
        choices=[
            ("sm", "Small"),
            ("md", "Medium"),
            ("lg", "Large"),
        ],
        default="md",
    )

    class Meta:
        icon = "link"
        label = "Button"
        template = "testapp/blocks/button.html"


class CallToActionBlock(blocks.StructBlock):
    """Wrapper for call-to-action buttons.

    Contains a ListBlock of buttons so each button is individually inspectable
    (each ListChild gets a UUID) while maintaining clean template syntax in
    parent blocks (can still use {% include_block value.cta %}).
    """

    buttons = blocks.ListBlock(
        ButtonBlock(),
        min_num=0,
        max_num=3,
        label="Buttons",
        help_text="Add one or more call-to-action buttons",
    )

    class Meta:
        icon = "link"
        label = "Call to Action"
        template = "testapp/blocks/cta.html"


class HeroSectionBlock(blocks.StructBlock):
    """Full-width hero section with a heading, optional subheading and body copy,
    and an optional call-to-action button.
    """

    heading = blocks.CharBlock(max_length=200, default="Welcome to our platform")
    subheading = blocks.CharBlock(
        max_length=400,
        required=False,
        default="Discover powerful tools to transform your workflow",
    )
    body = blocks.RichTextBlock(
        required=False,
        default="<p>Start building amazing experiences today with our comprehensive suite of features designed for modern teams.</p>",
    )
    buttons = blocks.ListBlock(ButtonBlock(), min_num=0, max_num=2, label="Buttons")

    class Meta:
        icon = "image"
        label = "Hero Section"
        template = "testapp/blocks/hero_section.html"


# New CMS Blocks migrated from React/Shadcn


class BadgeBlock(blocks.StructBlock):
    """Small label/tag for sections."""

    text = blocks.CharBlock(max_length=100, default="New Feature")
    variant = blocks.ChoiceBlock(
        choices=[
            ("default", "Default"),
            ("highlight", "Highlight"),
            ("muted", "Muted"),
        ],
        default="default",
    )

    class Meta:
        icon = "tag"
        label = "Badge"
        template = "testapp/blocks/badge.html"


class EnhancedHeroSectionBlock(blocks.StructBlock):
    """Enhanced hero section with badge, alignment, image, and dual CTAs."""

    badge = blocks.CharBlock(max_length=50, required=False, default="Introducing")
    headline = blocks.CharBlock(
        max_length=200,
        default="Build amazing experiences with our platform",
    )
    description = blocks.TextBlock(
        default="Powerful tools and features to help you create, manage, and scale your content with ease. Join thousands of teams already using our platform."
    )
    buttons = blocks.ListBlock(ButtonBlock(), min_num=0, max_num=2, label="Buttons")
    image = blocks.StructBlock(
        [
            ("image", ImageChooserBlock(required=False)),
            (
                "alt",
                blocks.CharBlock(max_length=255, required=False, default="Hero image"),
            ),
        ],
        required=False,
        label="Hero Image",
    )
    alignment = blocks.ChoiceBlock(
        choices=[
            ("left", "Left"),
            ("center", "Center"),
        ],
        default="center",
    )

    class Meta:
        icon = "image"
        label = "Enhanced Hero Section"
        template = "testapp/blocks/enhanced_hero_section.html"


class FeatureItemBlock(blocks.StructBlock):
    """Single feature card with icon, title, and description."""

    icon = blocks.CharBlock(
        max_length=10,
        help_text="Emoji or icon character (e.g., 🚀, ⚡, 💡)",
        default="⚡",
    )
    title = blocks.CharBlock(max_length=100, default="Lightning Fast")
    description = blocks.TextBlock(
        default="Built for speed and performance. Experience instant page loads and seamless interactions."
    )

    class Meta:
        icon = "pick"
        label = "Feature"
        template = "testapp/blocks/feature_item.html"


class FeatureGridBlock(blocks.StructBlock):
    """Grid of feature cards with icons, titles, and descriptions."""

    badge = blocks.CharBlock(max_length=50, required=False, default="Features")
    headline = blocks.CharBlock(max_length=200, default="Everything you need to succeed")
    description = blocks.TextBlock(
        required=False,
        default="Powerful features designed to help you work smarter and faster.",
    )
    columns = blocks.ChoiceBlock(
        choices=[
            ("2", "2 columns"),
            ("3", "3 columns"),
            ("4", "4 columns"),
        ],
        default="3",
    )
    features = blocks.ListBlock(FeatureItemBlock(), min_num=1, max_num=12)
    background = blocks.ChoiceBlock(
        choices=[
            ("default", "Default"),
            ("surface", "Surface"),
            ("secondary", "Secondary"),
        ],
        default="default",
    )

    class Meta:
        icon = "grip"
        label = "Feature Grid"
        template = "testapp/blocks/feature_grid.html"


class PricingPlanBlock(blocks.StructBlock):
    """Single pricing plan card."""

    name = blocks.CharBlock(max_length=100, default="Professional")
    price = blocks.CharBlock(max_length=50, help_text="e.g., $29/mo", default="$29/mo")
    description = blocks.TextBlock(default="Perfect for growing teams and businesses")
    features = blocks.ListBlock(
        blocks.CharBlock(max_length=200, default="Unlimited projects"),
        label="Features",
    )
    cta = ButtonBlock(label="Call to Action")
    highlighted = blocks.BooleanBlock(
        required=False,
        default=False,
        help_text="Highlight this plan with special styling",
    )

    class Meta:
        icon = "tag"
        label = "Pricing Plan"
        template = "testapp/blocks/pricing_plan.html"


class PricingSectionBlock(blocks.StructBlock):
    """Pricing cards with feature lists."""

    badge = blocks.CharBlock(max_length=50, required=False, default="Pricing")
    headline = blocks.CharBlock(max_length=200, default="Choose your plan")
    description = blocks.TextBlock(
        required=False,
        default="Simple, transparent pricing that grows with you. Try any plan free for 14 days.",
    )
    plans = blocks.ListBlock(PricingPlanBlock(), min_num=1, max_num=4)
    background = blocks.ChoiceBlock(
        choices=[
            ("default", "Default"),
            ("surface", "Surface"),
            ("secondary", "Secondary"),
        ],
        default="default",
    )

    class Meta:
        icon = "tag"
        label = "Pricing Section"
        template = "testapp/blocks/pricing_section.html"


class StatItemBlock(blocks.StructBlock):
    """Single statistic with value and label."""

    value = blocks.CharBlock(max_length=50, help_text="e.g., 99.9%, 10k+, $1M", default="99.9%")
    label = blocks.CharBlock(max_length=100, default="Uptime")

    class Meta:
        icon = "snippet"
        label = "Stat"
        template = "testapp/blocks/stat_item.html"


class StatsSectionBlock(blocks.StructBlock):
    """Key metrics/stats display."""

    badge = blocks.CharBlock(max_length=50, required=False, default="By the numbers")
    headline = blocks.CharBlock(max_length=200, required=False, default="Trusted by teams worldwide")
    stats = blocks.ListBlock(StatItemBlock(), min_num=1, max_num=8)
    background = blocks.ChoiceBlock(
        choices=[
            ("default", "Default"),
            ("surface", "Surface"),
            ("secondary", "Secondary"),
        ],
        default="surface",
    )

    class Meta:
        icon = "snippet"
        label = "Stats Section"
        template = "testapp/blocks/stats_section.html"


class TestimonialItemBlock(blocks.StructBlock):
    """Single testimonial card."""

    quote = blocks.TextBlock(
        default="This platform has completely transformed how we work. The tools are intuitive and powerful."
    )
    author = blocks.CharBlock(max_length=100, default="Sarah Johnson")
    role = blocks.CharBlock(max_length=100, default="Head of Product, TechCorp")
    avatar = ImageChooserBlock(required=False)

    class Meta:
        icon = "openquote"
        label = "Testimonial"
        template = "testapp/blocks/testimonial_item.html"


class TestimonialSectionBlock(blocks.StructBlock):
    """Customer testimonials grid."""

    badge = blocks.CharBlock(max_length=50, required=False, default="Testimonials")
    headline = blocks.CharBlock(max_length=200, default="Loved by teams everywhere")
    testimonials = blocks.ListBlock(TestimonialItemBlock(), min_num=1, max_num=6)
    background = blocks.ChoiceBlock(
        choices=[
            ("default", "Default"),
            ("surface", "Surface"),
            ("secondary", "Secondary"),
        ],
        default="surface",
    )

    class Meta:
        icon = "openquote"
        label = "Testimonial Section"
        template = "testapp/blocks/testimonial_section.html"


class TextWithImageBlock(blocks.StructBlock):
    """Side-by-side text and image section."""

    badge = blocks.CharBlock(max_length=50, required=False, default="How it works")
    headline = blocks.CharBlock(max_length=200, default="Built for creators and teams")
    description = blocks.TextBlock(
        default="Our platform brings together everything you need to create, collaborate, and publish. From idea to execution, we've got you covered with powerful tools designed for modern teams."
    )
    image = blocks.StructBlock(
        [
            ("image", ImageChooserBlock()),
            (
                "alt",
                blocks.CharBlock(max_length=255, required=False, default="Feature illustration"),
            ),
        ],
        label="Image",
    )
    image_position = blocks.ChoiceBlock(
        choices=[
            ("left", "Left"),
            ("right", "Right"),
        ],
        default="right",
        label="Image position",
    )
    cta = ButtonBlock(required=False, label="Call to Action")
    background = blocks.ChoiceBlock(
        choices=[
            ("default", "Default"),
            ("surface", "Surface"),
            ("secondary", "Secondary"),
        ],
        default="default",
    )

    class Meta:
        icon = "doc-full"
        label = "Text with Image"
        template = "testapp/blocks/text_with_image.html"


class LogoItemBlock(blocks.StructBlock):
    """Single logo with optional link."""

    image = ImageChooserBlock()
    alt = blocks.CharBlock(max_length=255, default="Partner logo")
    href = blocks.URLBlock(required=False, label="Link URL", default="https://example.com")

    class Meta:
        icon = "image"
        label = "Logo"
        template = "testapp/blocks/logo_item.html"


class LogoCloudBlock(blocks.StructBlock):
    """Row of partner/client logos."""

    headline = blocks.CharBlock(
        max_length=200,
        required=False,
        default="Trusted by leading companies",
    )
    logos = blocks.ListBlock(LogoItemBlock(), min_num=1, max_num=12)
    background = blocks.ChoiceBlock(
        choices=[
            ("default", "Default"),
            ("surface", "Surface"),
            ("secondary", "Secondary"),
        ],
        default="default",
    )

    class Meta:
        icon = "image"
        label = "Logo Cloud"
        template = "testapp/blocks/logo_cloud.html"


class ContentBlock(blocks.StreamBlock):
    """One list row inside ContainerBlock: a stream so templates can use
    ``{% for block in item %}{% include_block block %}``.
    """

    logo_cloud = LogoCloudBlock()

    class Meta:
        icon = "dots-horizontal"
        label = "Column content"


class ContainerBlock(blocks.StructBlock):
    """Regression fixture: ListBlock of StreamBlock columns for wagtail-inspect
    (nested ``ListValue`` iteration + inner stream ``include_block``).
    """

    content = blocks.ListBlock(
        ContentBlock(),
        min_num=1,
        max_num=4,
        label="Content",
    )

    class Meta:
        icon = "placeholder"
        label = "Container"
        template = "testapp/blocks/container.html"


class CTABannerBlock(blocks.StructBlock):
    """Full-width call-to-action banner."""

    headline = blocks.CharBlock(max_length=200, default="Ready to get started?")
    description = blocks.TextBlock(
        required=False,
        default="Join thousands of teams already using our platform. Start your free trial today.",
    )
    buttons = blocks.ListBlock(
        ButtonBlock(),
        min_num=0,
        max_num=3,
        label="Buttons",
        help_text="Add one or more call-to-action buttons",
    )
    variant = blocks.ChoiceBlock(
        choices=[
            ("default", "Default"),
            ("primary", "Primary"),
        ],
        default="primary",
    )

    class Meta:
        icon = "pick"
        label = "CTA Banner"
        template = "testapp/blocks/cta_banner.html"


class FAQItemBlock(blocks.StructBlock):
    """Single FAQ item with question and answer."""

    question = blocks.CharBlock(max_length=200, default="How does this work?")
    answer = blocks.TextBlock(
        default="Our platform is designed to be intuitive and easy to use. Simply sign up, create your first project, and start collaborating with your team right away."
    )

    class Meta:
        icon = "help"
        label = "FAQ Item"
        template = "testapp/blocks/faq_item.html"


class FAQSectionBlock(blocks.StructBlock):
    """Frequently asked questions with expandable answers."""

    badge = blocks.CharBlock(max_length=50, required=False, default="FAQ")
    headline = blocks.CharBlock(max_length=200, default="Frequently asked questions")
    description = blocks.TextBlock(
        required=False,
        default="Everything you need to know about our platform. Can't find the answer you're looking for? Contact our support team.",
    )
    faqs = blocks.ListBlock(FAQItemBlock(), min_num=1, max_num=20)
    background = blocks.ChoiceBlock(
        choices=[
            ("default", "Default"),
            ("surface", "Surface"),
            ("secondary", "Secondary"),
        ],
        default="default",
    )

    class Meta:
        icon = "help"
        label = "FAQ Section"
        template = "testapp/blocks/faq_section.html"


class FooterLinkBlock(blocks.StructBlock):
    """Single footer link."""

    label = blocks.CharBlock(max_length=100, default="About Us")
    url = blocks.URLBlock(default="https://example.com")

    class Meta:
        label = "Footer Link"


class FooterColumnBlock(blocks.StructBlock):
    """Footer column with title and links."""

    title = blocks.CharBlock(max_length=100, default="Company")
    links = blocks.ListBlock(FooterLinkBlock())

    class Meta:
        icon = "list-ul"
        label = "Footer Column"


class FooterSectionBlock(blocks.StructBlock):
    """Site footer with columns of links."""

    brand_text = blocks.CharBlock(
        max_length=100,
        help_text="Brand name or tagline",
        default="YourBrand",
    )
    description = blocks.TextBlock(
        required=False,
        default="Building the future of content management, one block at a time.",
    )
    columns = blocks.ListBlock(FooterColumnBlock(), max_num=4)
    copyright = blocks.CharBlock(
        max_length=200,
        default="© 2026 YourBrand. All rights reserved.",
    )

    class Meta:
        icon = "bars"
        label = "Footer Section"
        template = "testapp/blocks/footer_section.html"


class RichTextSectionBlock(blocks.StructBlock):
    """Prose/article content block for long-form text."""

    content = blocks.RichTextBlock(
        default="<p>Add your content here. This section supports rich text formatting including <strong>bold</strong>, <em>italic</em>, links, lists, and more.</p>"
    )
    max_width = blocks.ChoiceBlock(
        choices=[
            ("sm", "Small (640px)"),
            ("md", "Medium (768px)"),
            ("lg", "Large (1024px)"),
        ],
        default="md",
    )
    background = blocks.ChoiceBlock(
        choices=[
            ("default", "Default"),
            ("surface", "Surface"),
            ("secondary", "Secondary"),
        ],
        default="default",
    )

    class Meta:
        icon = "doc-full"
        label = "Rich Text Section"
        template = "testapp/blocks/rich_text_section.html"


class TagListBlock(blocks.StructBlock):
    """Renders a list of tags WITHOUT {% include_block %}, so individual tag
    items cannot be annotated by the Python BoundBlock patches. This block
    exists to exercise the JS augmentation pipeline in E2E tests.
    """

    heading = blocks.CharBlock(max_length=100, default="Tags")
    tags = blocks.ListBlock(
        blocks.StructBlock(
            [("label", blocks.CharBlock(max_length=50))],
            label="Tag",
        ),
        min_num=1,
        label="Tags",
    )

    class Meta:
        icon = "tag"
        label = "Tag List"
        template = "testapp/blocks/tag_list.html"
