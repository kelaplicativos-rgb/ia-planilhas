from __future__ import annotations

import pandas as pd

from bling_app_zero.core.final_output_rule_engine import apply_final_output_rules
from bling_app_zero.core.final_video_link_guard import apply_video_link_guard_resource, is_video_link


def test_video_link_guard_removes_video_from_image_column() -> None:
    df = pd.DataFrame([
        {
            'Produto': 'A',
            'URL Imagens Externas': 'https://img.com/a.jpg|https://youtu.be/abc123|https://img.com/b.jpg',
        }
    ])

    result = apply_video_link_guard_resource(df)

    assert result.video_links_removed == 1
    assert result.df['URL Imagens Externas'].tolist() == ['https://img.com/a.jpg|https://img.com/b.jpg']


def test_video_column_is_cleared() -> None:
    df = pd.DataFrame([{'Produto': 'A', 'Video': 'https://youtube.com/watch?v=abc'}])

    result = apply_video_link_guard_resource(df)

    assert result.video_links_removed == 1
    assert result.df['Video'].tolist() == ['']


def test_final_output_rules_remove_video_before_download_or_api() -> None:
    df = pd.DataFrame([
        {
            'Produto': 'A',
            'URL Imagens Externas': 'https://img.com/a.jpg|https://site.com/video.mp4',
            'Link Externo': 'https://loja.com/produto-a',
        }
    ])

    fixed_df, report = apply_final_output_rules(df, context='api')

    assert report.video_links_removed == 1
    assert fixed_df['URL Imagens Externas'].tolist() == ['https://img.com/a.jpg']
    assert fixed_df['Link Externo'].tolist() == ['https://loja.com/produto-a']


def test_video_link_detection() -> None:
    assert is_video_link('https://vimeo.com/123')
    assert is_video_link('https://cdn.site.com/movie.webm')
    assert not is_video_link('https://loja.com/produto-a')
