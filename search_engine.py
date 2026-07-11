"""
Lightweight, low-resource file search and content retrieval system.
Rule-based search primary (~80%), AI summarization secondary (~20%).
"""
import os
import re
import time
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from pypdf import PdfReader
from core import LLMClient

logger = logging.getLogger(__name__)


def extract_text_from_file(file_path: str) -> List[Tuple[int, str]]:
    """Extract text from PDF, MD, or TXT file. Returns list of (page_num, text)."""
    ext = Path(file_path).suffix.lower()
    try:
        if ext == '.pdf':
            reader = PdfReader(file_path)
            pages = []
            for i, page in enumerate(reader.pages):
                text = page.extract_text()
                if text and text.strip():
                    pages.append((i + 1, text))
            return pages
        elif ext in ('.md', '.txt'):
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                text = f.read()
            return [(1, text)] if text.strip() else []
    except Exception as e:
        logger.warning(f"Could not extract text from {file_path}: {e}")
        return []


class FileScanner:
    """Scans folders for supported files and builds a searchable manifest."""

    SUPPORTED_EXTS = {'.pdf', '.md', '.txt'}

    def __init__(self):
        self.cache = {}

    def scan_folder(self, folder_path: str) -> List[Dict]:
        """Recursively scan folder for supported files, return manifest."""
        files = []
        for root, dirs, filenames in os.walk(folder_path):
            for fname in filenames:
                ext = Path(fname).suffix.lower()
                if ext in self.SUPPORTED_EXTS:
                    fpath = os.path.join(root, fname)
                    stat = os.stat(fpath)
                    files.append({
                        'path': fpath,
                        'filename': fname,
                        'folder': root,
                        'ext': ext,
                        'size_kb': round(stat.st_size / 1024, 1),
                        'modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    })
        return files

    def scan_multiple_roots(self, roots: List[str]) -> List[Dict]:
        """Scan multiple root directories for cross-location search."""
        all_files = []
        seen = set()
        for root in roots:
            if os.path.isdir(root):
                for f in self.scan_folder(root):
                    if f['path'] not in seen:
                        seen.add(f['path'])
                        all_files.append(f)
        return all_files


class RuleBasedSearcher:
    """
    Core rule-based search engine.
    Uses regex to find keyword matches in extracted text.
    No AI involved — 100% rule-based.
    """

    def __init__(self):
        self.context_chars = 300  # characters before/after match

    def search_single_file(self, file_path: str, keyword: str) -> List[Dict]:
        """Search a single file for keyword, return match segments with context."""
        pages = extract_text_from_file(file_path)
        if not pages:
            return []

        pattern = re.compile(re.escape(keyword), re.IGNORECASE)
        results = []
        filename = os.path.basename(file_path)
        folder = os.path.basename(os.path.dirname(file_path))

        for page_num, text in pages:
            for match in pattern.finditer(text):
                start = max(0, match.start() - self.context_chars)
                end = min(len(text), match.end() + self.context_chars)

                before = text[start:match.start()]
                matched = text[match.start():match.end()]
                after = text[match.end():end]

                # Build excerpt with markers
                if start > 0:
                    before = '...' + before[-50:] if len(before) > 50 else before
                if end < len(text):
                    after = after[:50] + '...' if len(after) > 50 else after

                excerpt = f"{before}[{matched}]{after}"

                results.append({
                    'file_path': file_path,
                    'filename': filename,
                    'folder': folder,
                    'page': page_num,
                    'keyword': keyword,
                    'excerpt': excerpt,
                    'full_context': text[max(0, match.start() - 500):min(len(text), match.end() + 500)],
                    'match_start': match.start(),
                    'match_end': match.end(),
                    'score': 1.0,
                })

                if len(results) >= 20:
                    break
            if len(results) >= 20:
                break

        return results

    def search_files(self, file_paths: List[str], keyword: str) -> List[Dict]:
        """Search multiple files, return all matches ranked by relevance."""
        all_results = []
        for fpath in file_paths:
            try:
                matches = self.search_single_file(fpath, keyword)
                all_results.extend(matches)
            except Exception as e:
                logger.warning(f"Error searching {fpath}: {e}")

        # Rank: more matches per file = higher relevance
        file_match_count = {}
        for r in all_results:
            file_match_count[r['file_path']] = file_match_count.get(r['file_path'], 0) + 1

        for r in all_results:
            r['score'] = r.get('score', 1.0) * (1 + file_match_count[r['file_path']] * 0.1)

        all_results.sort(key=lambda x: x['score'], reverse=True)
        return all_results

    def locate_keyword_in_doc(self, file_path: str, keyword: str) -> Dict:
        """Find exact position of keyword in a document.
        Returns the best matching segment with surrounding context.
        Used when user asks for specific info (e.g. 'author name in Q3_report.pdf')."""
        matches = self.search_single_file(file_path, keyword)
        if not matches:
            return {'found': False, 'text': '', 'page': 0}
        # Return the first (best) match's context
        best = matches[0]
        return {
            'found': True,
            'text': best['full_context'],
            'page': best['page'],
            'excerpt': best['excerpt'],
        }


class LightweightSummarizer:
    """
    AI-powered summarization — used ONLY on pre-located text segments.
    This is the ~20% AI processing cap.
    Runs on Qwen3:0.6B (low-resource) or Qwen2.5:3B (high-resource).
    """

    def __init__(self, config):
        self.config = config
        self.client = LLMClient()

    def _get_model(self) -> str:
        """Return the primary model for search summarization."""
        return self.config.models.get('search_chat', self.config.models['chat'])

    def _get_fallback_model(self) -> str:
        """Return the fallback model for local Ollama."""
        return self.config.models.get('search_chat_fallback', self.config.models.get('chat_fallback', 'qwen3:0.6b'))

    def summarize_segment(self, text: str, query: str, max_tokens: int = 256) -> str:
        """
        Summarize a pre-located text segment to answer a specific query.
        Used ONLY after rule-based search has found the relevant segment.
        AI processes a small window, not the whole document.
        """
        if not text or not text.strip():
            return "No relevant content found."

        prompt = (
            f"Extract only the information relevant to this question from the text below. "
            f"Keep your answer brief and directly from the text.\n\n"
            f"Question: {query}\n\n"
            f"Text:\n{text[:2000]}\n\n"
            f"Answer:"
        )

        try:
            response = self.client.generate(
                model=self._get_model(),
                fallback_model=self._get_fallback_model(),
                prompt=prompt,
                options={'temperature': 0.1, 'max_tokens': max_tokens, 'top_p': 0.5}
            )
            return response['response'].strip()
        except Exception as e:
            logger.warning(f"AI summarization failed: {e}")
            # Fallback: return raw excerpt
            return f"[AI unavailable] {text[:500]}..."

    def batch_summarize(self, segments: List[Dict], query: str) -> List[Dict]:
        """Summarize multiple pre-located segments.
        Only the top-N segments get AI processing."""
        results = []
        for i, seg in enumerate(segments[:5]):  # Cap at 5 segments
            summary = self.summarize_segment(seg['full_context'], query)
            results.append({**seg, 'ai_summary': summary})
        return results


class DualSearchEngine:
    """
    Coordinates rule-based and AI-powered search.
    Mode 'quick': rule-based only (fast, 0% AI).
    Mode 'smart': rule-based + AI summarization of top results (20% AI).
    Measures and reports performance for both.
    """

    def __init__(self, config):
        self.config = config
        self.scanner = FileScanner()
        self.searcher = RuleBasedSearcher()
        self.summarizer = LightweightSummarizer(config)

    def search(self, keyword: str, file_paths: List[str], mode: str = 'quick') -> Dict:
        """
        Perform search in specified mode.
        
        Args:
            keyword: Search term
            file_paths: List of files to search
            mode: 'quick' (rule-based) or 'smart' (rule-based + AI summary)
            
        Returns:
            Dict with results, timing, and mode info
        """
        start = time.time()

        # Phase 1: Rule-based keyword search (always runs, 0% AI)
        raw_results = self.searcher.search_files(file_paths, keyword)
        rule_time = time.time() - start

        if mode == 'quick':
            return {
                'mode': 'quick (rule-based)',
                'keyword': keyword,
                'total_matches': len(raw_results),
                'results': raw_results[:10],
                'timing': {'rule_search': round(rule_time, 3), 'total': round(rule_time, 3)},
                'ai_usage_pct': 0,
            }

        # Phase 2: AI summarization of top results (~20% AI)
        ai_start = time.time()
        ai_results = self.summarizer.batch_summarize(raw_results[:5], keyword)
        ai_time = time.time() - ai_start

        total_time = time.time() - start
        ai_pct = round((ai_time / total_time) * 100) if total_time > 0 else 0

        return {
            'mode': 'smart (rule-based + AI summary)',
            'keyword': keyword,
            'total_matches': len(raw_results),
            'results': ai_results,
            'timing': {
                'rule_search': round(rule_time, 3),
                'ai_summary': round(ai_time, 3),
                'total': round(total_time, 3),
            },
            'ai_usage_pct': min(ai_pct, 100),
        }

    def locate_in_document(self, file_path: str, keyword: str) -> Dict:
        """
        Locate a specific keyword in a specific document.
        Used for targeted queries like 'find the author in report.pdf'.
        Rule-based only — no AI unless explicitly requested.
        """
        start = time.time()
        result = self.searcher.locate_keyword_in_doc(file_path, keyword)
        elapsed = time.time() - start
        result['timing'] = round(elapsed, 3)
        return result


class CrossLocationFinder:
    """
    Cross-location file retrieval.
    Finds files across user storage that match a query.
    Uses file-level pattern matching first, then content search.
    """

    def __init__(self, config):
        self.config = config
        self.scanner = FileScanner()
        self.searcher = RuleBasedSearcher()

    def find_files_by_name(self, query: str, roots: List[str]) -> List[Dict]:
        """Find files whose names match the query (case-insensitive)."""
        keyword = query.lower()
        all_files = self.scanner.scan_multiple_roots(roots)
        matches = []
        for f in all_files:
            name_lower = f['filename'].lower()
            if keyword in name_lower:
                matches.append(f)
        return matches

    def find_files_by_content(self, query: str, roots: List[str]) -> List[Dict]:
        """
        Find files whose content contains the query.
        Scans all files in roots, returns matches with context.
        This is the cross-location content search.
        """
        all_files = self.scanner.scan_multiple_roots(roots)
        file_paths = [f['path'] for f in all_files]
        results = self.searcher.search_files(file_paths, query)

        # Group by file for summary
        file_summary = {}
        for r in results:
            fp = r['file_path']
            if fp not in file_summary:
                file_summary[fp] = {
                    'path': fp,
                    'filename': r['filename'],
                    'folder': r['folder'],
                    'match_count': 0,
                    'excerpts': [],
                }
            file_summary[fp]['match_count'] += 1
            if len(file_summary[fp]['excerpts']) < 3:
                file_summary[fp]['excerpts'].append(r['excerpt'])

        return sorted(file_summary.values(), key=lambda x: x['match_count'], reverse=True)

    def locate_folder(self, folder_name: str, roots: List[str]) -> List[str]:
        """Locate a folder by name across storage roots."""
        keyword = folder_name.lower()
        found = []
        for root in roots:
            for dirpath, dirnames, _ in os.walk(root):
                for d in dirnames:
                    if keyword in d.lower():
                        found.append(os.path.join(dirpath, d))
        return found
