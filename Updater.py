import wikipedia
from bs4 import BeautifulSoup
from datetime import datetime
import logging
import re

# Set up logging for debugging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

class EpisodeTableParser:
    """
    Robust parser for Wikipedia episode tables that handles varying structures
    """

    def __init__(self, series_name):
        self.series_name = series_name
        self.episodes = []

    def parse_table(self, html_content):
        """
        Parse episode tables from HTML content, handling various Wikipedia table formats
        """
        soup = BeautifulSoup(html_content, 'html.parser')

        # Find all tables - Wikipedia episode lists typically use wikitable class
        tables = soup.find_all('table', class_='wikitable')

        logger.info(f"Found {len(tables)} tables for {self.series_name}")

        for table_idx, table in enumerate(tables):
            try:
                self._parse_single_table(table, table_idx)
            except Exception as e:
                logger.warning(f"Failed to parse table {table_idx} for {self.series_name}: {e}")
                continue

        return self.episodes

    def _parse_single_table(self, table, table_idx):
        """
        Parse a single episode table, detecting column structure dynamically
        """
        rows = table.find_all('tr')
        if len(rows) < 2:
            return

        # Find header row and detect column structure
        header_row = rows[0]
        headers = [th.get_text(strip=True).lower() for th in header_row.find_all(['th', 'td'])]

        if not headers or 'title' not in ' '.join(headers):
            # Not an episode table
            return

        logger.info(f"Table {table_idx} headers: {headers}")

        # Detect column positions
        col_map = self._detect_columns(headers)

        if col_map['title'] is None:
            logger.warning(f"Could not find title column in table {table_idx}")
            return

        # Parse episode rows
        season_num = 1
        episode_in_season = 1
        episode_overall = 0

        for row_idx, row in enumerate(rows[1:], start=1):
            cells = row.find_all(['td', 'th'])

            if len(cells) == 0:
                continue

            # Skip if this looks like a header row
            cell_text = cells[0].get_text(strip=True).lower()
            if 'title' in cell_text or 'no.' in cell_text:
                continue

            try:
                episode_data = self._parse_episode_row(cells, col_map, season_num, episode_in_season, episode_overall)

                if episode_data:
                    for ep in episode_data['episodes']:
                        self.episodes.append(ep)

                    # Update counters
                    if episode_data['is_new_season']:
                        season_num = episode_data['season']
                        episode_in_season = episode_data['episode_count']
                    else:
                        episode_in_season += episode_data['episode_count']

                    episode_overall += episode_data['episode_count']

            except Exception as e:
                logger.debug(f"Failed to parse row {row_idx} in table {table_idx}: {e}")
                continue

    def _detect_columns(self, headers):
        """
        Detect which columns contain episode numbers, titles, etc.
        Returns a dict mapping column types to indices
        """
        col_map = {
            'no_overall': None,
            'no_in_season': None,
            'title': None,
            'has_single_no': False
        }

        for idx, header in enumerate(headers):
            header_lower = header.lower()

            # Title column
            if 'title' in header_lower:
                col_map['title'] = idx

            # Episode number columns - check for various formats
            elif 'no.overall' in header_lower or 'overall' in header_lower or header_lower == 'no.':
                if col_map['no_in_season'] is None:
                    col_map['no_overall'] = idx

            elif 'no.inseason' in header_lower.replace(' ', '') or 'no.in' in header_lower:
                col_map['no_in_season'] = idx

            elif header_lower == 'no.' and col_map['no_overall'] is None:
                col_map['no_overall'] = idx
                col_map['has_single_no'] = True

        return col_map

    def _parse_episode_row(self, cells, col_map, current_season, current_episode, current_overall):
        """
        Parse a single episode row, handling multi-part episodes
        """
        if len(cells) < max(filter(lambda x: x is not None,
                                   [col_map['title'], col_map['no_overall'] or 0, col_map['no_in_season'] or 0])) + 1:
            return None

        # Extract episode title
        title_cell = cells[col_map['title']]
        title = self._clean_text(title_cell.get_text())

        if not title or 'TBD' in title or 'TBA' in title:
            return None

        # Extract episode numbers
        episode_nums = self._extract_episode_numbers(cells, col_map)

        # Detect multi-part episodes
        is_multi_part = self._is_multi_part_episode(cells, col_map)

        # Determine season number
        season = current_season
        episode_in_season = episode_nums.get('in_season', current_episode)

        # Check if this is a new season (episode 1)
        is_new_season = False
        if episode_in_season == 1 and current_overall > 0:
            season = current_season + 1
            is_new_season = True

        # Build episode list
        episodes = []

        if is_multi_part and episode_in_season is not None:
            # Multi-part episode
            episodes.append(f"S{season}E{episode_in_season:02d} {title} Part I")
            episodes.append(f"S{season}E{episode_in_season+1:02d} {title} Part II")
            episode_count = 2
        else:
            # Single episode
            if episode_in_season is not None:
                episodes.append(f"S{season}E{episode_in_season:02d} {title}")
                episode_count = 1
            else:
                # Pilot or special
                episodes.append(f"S0E{current_overall+1:02d} {title}")
                episode_count = 1

        return {
            'episodes': episodes,
            'season': season,
            'episode_count': episode_count,
            'is_new_season': is_new_season
        }

    def _extract_episode_numbers(self, cells, col_map):
        """
        Extract episode numbers from cells, handling various formats
        """
        nums = {'overall': None, 'in_season': None}

        # Try to extract overall episode number
        if col_map['no_overall'] is not None and col_map['no_overall'] < len(cells):
            overall_text = cells[col_map['no_overall']].get_text(strip=True)
            nums['overall'] = self._extract_first_number(overall_text)

        # Try to extract episode in season number
        if col_map['no_in_season'] is not None and col_map['no_in_season'] < len(cells):
            season_text = cells[col_map['no_in_season']].get_text(strip=True)
            nums['in_season'] = self._extract_first_number(season_text)
        elif col_map['has_single_no'] and col_map['no_overall'] is not None:
            # Single number column - use it as episode in season
            nums['in_season'] = nums['overall']

        return nums

    def _extract_first_number(self, text):
        """
        Extract the first number from text, handling ranges (e.g., "1-2" returns 1)
        """
        if not text:
            return None

        # Remove non-numeric characters except dash and numbers
        # Look for patterns like "1", "01", "1-2", "1–2"
        match = re.search(r'(\d+)', text)
        if match:
            return int(match.group(1))

        return None

    def _is_multi_part_episode(self, cells, col_map):
        """
        Detect if this is a multi-part episode based on separators in cells
        """
        # Check for horizontal rules or dashes in number cells
        for col_idx in [col_map['no_overall'], col_map['no_in_season']]:
            if col_idx is not None and col_idx < len(cells):
                cell = cells[col_idx]
                # Check for <hr> tag
                if cell.find('hr'):
                    return True
                # Check for dash/endash in text
                text = cell.get_text(strip=True)
                if '–' in text or '-' in text:
                    # Make sure it's not just a negative number
                    if re.search(r'\d+[–-]\d+', text):
                        return True

        return False

    def _clean_text(self, text):
        """
        Clean episode title text
        """
        # Remove citations like [1], [2]
        text = re.sub(r'\[\d+\]', '', text)
        # Remove extra whitespace
        text = ' '.join(text.split())
        # Remove quotes
        text = text.replace('"', '').replace("'", '')
        # Replace non-breaking spaces
        text = text.replace('\xa0', ' ')

        return text.strip()


class MovieParser:
    """
    Parser for Star Trek movie lists
    """

    def __init__(self):
        self.movies_by_era = {}

    def parse_movie_page(self, html_content):
        """
        Parse movie list from Wikipedia - looks for specific film era sections
        """
        soup = BeautifulSoup(html_content, 'html.parser')

        # Find all h2/h3 headers
        headers = soup.find_all(['h2', 'h3'])

        for header in headers:
            header_text = header.get_text(strip=True)
            # Remove [edit] links
            header_text = re.sub(r'\[edit\]', '', header_text).strip()

            # Only process headers that look like film eras
            # Must contain "film" and should be a section header (not a subsection about plot, cast, etc.)
            if not self._is_valid_film_era_header(header_text):
                continue

            logger.info(f"Found film era header: {header_text}")

            # Find the next content after this header (before the next header)
            movies = self._extract_movies_after_header(header)

            if movies:
                self.movies_by_era[header_text] = movies
                logger.info(f"  Found {len(movies)} movies in this era")

        return self.movies_by_era

    def _is_valid_film_era_header(self, header_text):
        """
        Check if a header represents a valid film era section
        """
        header_lower = header_text.lower()

        # Must contain 'film'
        if 'film' not in header_lower:
            return False

        # Should be a main section, not a subsection
        # Valid examples: "The Original Series films", "Kelvin timeline films"
        # Invalid examples: "Film production", "Filmography", specific movie titles

        # Exclude specific movie titles (they usually have years or colons)
        if re.search(r'\(\d{4}\)', header_text):  # Has a year like (2009)
            return False

        # Exclude common subsection headers
        exclude_keywords = ['production', 'development', 'cast', 'crew', 'reception',
                           'box office', 'releases', 'home media', 'soundtrack',
                           'plot', 'premise', 'setting', 'characters', 'critical',
                           'cancelled', 'unmade', 'potential', 'future']

        for keyword in exclude_keywords:
            if keyword in header_lower:
                return False

        # Must be a section about multiple films (plural or "timeline")
        if 'films' in header_lower or 'timeline' in header_lower:
            return True

        return False

    def _extract_movies_after_header(self, header):
        """
        Extract movie titles from the content following a header
        """
        movies = []

        # Get the parent section
        section = header.find_next_sibling()

        # Look through siblings until we hit another header
        while section and section.name not in ['h1', 'h2', 'h3']:
            # Look for list items
            if section.name in ['ul', 'ol']:
                for li in section.find_all('li', recursive=False):
                    movie = self._extract_movie_from_list_item(li)
                    if movie:
                        movies.append(movie)

            # Also check if this section contains lists
            for list_elem in section.find_all(['ul', 'ol'], recursive=True):
                for li in list_elem.find_all('li', recursive=False):
                    movie = self._extract_movie_from_list_item(li)
                    if movie and movie not in movies:  # Avoid duplicates
                        movies.append(movie)

            section = section.find_next_sibling()

        return movies

    def _extract_movie_from_list_item(self, li):
        """
        Extract a movie title from a list item
        """
        text = li.get_text(strip=True)

        # Remove citations
        text = re.sub(r'\[\d+\]', '', text)
        text = text.strip()

        # Movies should have a year in parentheses
        if not re.search(r'\(\d{4}\)', text):
            return None

        # Should start with "Star Trek" (most movies do)
        if not text.startswith('Star Trek'):
            return None

        # Extract just the movie title with year
        # Format is usually: "Star Trek: Movie Title (2009) - description"
        # We want: "Star Trek: Movie Title (2009)"
        match = re.match(r'(Star Trek[^(]*\(\d{4}\))', text)
        if match:
            return match.group(1).strip()

        return None


def _extract_series_name(page_title):
    """
    Extract clean series name from Wikipedia page title
    Examples:
        "List of Star Trek: The Original Series episodes" -> "The Original Series"
        "List of Star Trek: Discovery episodes" -> "Discovery"
        "List of Star Trek: The Animated Series episodes" -> "The Animated Series"
    """
    # Remove common prefixes and suffixes
    name = page_title.replace('List of ', '', 1)
    name = name.replace(' episodes', '')

    # If there's a colon, take everything after "Star Trek:"
    if 'Star Trek:' in name:
        name = name.split('Star Trek:', 1)[1].strip()
    else:
        # No colon, just remove "Star Trek"
        name = name.replace('Star Trek', '').strip()

    return name if name else page_title


def _create_array_name(media_name, suffix):
    """
    Create a valid Python array name from a media name
    Examples:
        "The Original Series", "episodes" -> "TOSepisodes"
        "Discovery", "episodes" -> "Depisodes"
        "The Next Generation films", "movies" -> "TNGmovies"
    """
    # Known abbreviations for common series/eras
    abbreviations = {
        'The Original Series': 'TOS',
        'The Animated Series': 'TAS',
        'The Next Generation': 'TNG',
        'Deep Space Nine': 'DSN',
        'Voyager': 'V',
        'Enterprise': 'E',
        'Discovery': 'D',
        'Short Treks': 'ST',
        'Picard': 'P',
        'Lower Decks': 'LD',
        'Prodigy': 'P',
        'Strange New Worlds': 'SNW',
        'The Original Series films': 'TOS',
        'The Next Generation films': 'TNG',
        'Reboot (Kelvin timeline) films': 'RK',
        'Kelvin timeline films': 'RK',
    }

    # Check if we have a known abbreviation
    for full_name, abbr in abbreviations.items():
        if full_name.lower() in media_name.lower():
            return abbr + suffix

    # Fallback: use uppercase letters from the name
    uppercase_letters = ''.join(list(filter(lambda x: x.isupper(), media_name)))

    if len(uppercase_letters) >= 2:
        return uppercase_letters + suffix

    # Fallback: use first letter of each word
    words = media_name.split()
    initials = ''.join([w[0].upper() for w in words if w])

    if initials:
        return initials + suffix

    # Last resort: use a sanitized version of the name
    sanitized = media_name.replace(' ', '').replace('-', '').replace(':', '')
    return sanitized[:10] + suffix


def main():
    try:
        TVShows = {}
        Movies = {}

        logger.info("Starting Star Trek media update...")

        # Get direct references to the episode & films lists
        main_page = wikipedia.page("Star Trek", auto_suggest=False)

        for media_list in main_page.links:
            media_list_lower = media_list.lower()

            # Process Star Trek Films
            if 'star trek films' in media_list_lower or 'list of star trek films' in media_list_lower:
                logger.info(f'Processing films from: {media_list}')
                try:
                    film_page = wikipedia.page(media_list, auto_suggest=False)
                    movie_parser = MovieParser()
                    Movies = movie_parser.parse_movie_page(film_page.html())
                    logger.info(f"Found {len(Movies)} movie eras")
                except Exception as e:
                    logger.error(f"Failed to parse films from {media_list}: {e}")

            # Process Star Trek Episodes
            elif 'star trek episodes' in media_list_lower or 'list of star trek episodes' in media_list_lower:
                logger.info(f'Processing episodes from: {media_list}')
                try:
                    episode_hub_page = wikipedia.page(media_list, auto_suggest=False)

                    # Look for individual series episode lists
                    for series_link in episode_hub_page.links:
                        series_link_lower = series_link.lower()

                        if 'episodes' in series_link_lower and 'list of' in series_link_lower:
                            logger.info(f'  Processing series: {series_link}')

                            try:
                                series_page = wikipedia.page(series_link, auto_suggest=False)

                                # Extract series name from title
                                # e.g., "List of Star Trek: The Original Series episodes" -> "The Original Series"
                                series_name = _extract_series_name(series_link)

                                # Parse episodes
                                parser = EpisodeTableParser(series_name)
                                episodes = parser.parse_table(series_page.html())

                                if episodes:
                                    TVShows[series_name] = episodes
                                    logger.info(f"  Found {len(episodes)} episodes for {series_name}")
                                else:
                                    logger.warning(f"  No episodes found for {series_name}")

                            except wikipedia.exceptions.PageError:
                                logger.warning(f"  Could not find page: {series_link}")
                            except Exception as e:
                                logger.error(f"  Failed to parse {series_link}: {e}")

                except Exception as e:
                    logger.error(f"Failed to process episode hub {media_list}: {e}")

        # Debugging output
        logger.info(f"\nTotal TV Shows found: {len(TVShows)}")
        for show, episodes in TVShows.items():
            logger.info(f"  {show}: {len(episodes)} episodes")

        logger.info(f"\nTotal Movie eras found: {len(Movies)}")
        for era, movies in Movies.items():
            logger.info(f"  {era}: {len(movies)} movies")

        if not TVShows and not Movies:
            logger.error("No data was scraped! Please check Wikipedia page structure.")
            return

        # Update the StarTrekMediaPicker.py script
        logger.info('\nReading StarTrekMediaPicker.py script...')
        with open("StarTrekMediaPicker.py", "r", encoding='utf-8') as file:
            script = file.read()

        # Update Movies and TV Shows
        for media_type in [Movies, TVShows]:
            mapping_array = []
            is_film = media_type == Movies

            for media_name, media_list in media_type.items():
                media_type_name = 'movies' if is_film else 'episodes'

                # Create array name from media name
                media_array_name = _create_array_name(media_name, media_type_name)

                # Make sure we don't end up with duplicate array names
                instance_count = 1
                original_name = media_array_name
                while media_array_name in mapping_array:
                    media_array_name = original_name + str(instance_count)
                    instance_count += 1

                mapping_array.append(media_array_name)

                # Update script with new array if it doesn't exist
                if media_array_name not in script:
                    if is_film:
                        end_index = script.index('Movies') + len('Movies')
                    else:
                        end_index = script.index('Episodes') + len('Episodes')

                    script = script[:end_index] + '\n\n' + media_array_name + ' = []' + script[end_index:]

                # Update script with new array elements
                if media_array_name in script:
                    start_index = script.index(media_array_name)
                    end_index = start_index + script[start_index:].index(']')

                    replacement = media_array_name + ' = [\n'

                    for media_piece in media_list:
                        if 'TBD' in media_piece or 'TBA' in media_piece:
                            continue

                        replacement += f"   '{media_piece}',\n"

                    replacement += ']'

                    script = script[:start_index] + replacement + script[end_index + 1:]

            # Update mapping array
            mapping_count = 0
            if is_film:
                start_index = script.index('MovieMapping')
                replacement = 'MovieMapping = {\n'
            else:
                start_index = script.index('TVMapping')
                replacement = 'TVMapping = {\n'

            end_index = start_index + script[start_index:].index('}')

            for mapping in mapping_array:
                replacement += f'\t{mapping_count} : {mapping},\n'
                mapping_count += 1

            replacement += '}'

            script = script[:start_index] + replacement + script[end_index + 1:]

        # Update labels for movies
        if Movies:
            start_index = script.index('movieSeries')
            end_index = start_index + script[start_index:].index(']')
            replacement = 'movieSeries = [\n'
            for era in Movies.keys():
                replacement += f"   '{era}',\n"
            replacement += ']'
            script = script[:start_index] + replacement + script[end_index + 1:]

        # Update labels for TV shows
        if TVShows:
            start_index = script.index('series')
            end_index = start_index + script[start_index:].index(']')
            replacement = 'series = [\n'
            for show in TVShows.keys():
                replacement += f"   '{show}',\n"
            replacement += ']'
            script = script[:start_index] + replacement + script[end_index + 1:]

        # Write updated script
        logger.info('Writing updated script...')
        with open("StarTrekMediaPicker.py", "w", encoding='utf-8') as file:
            file.write(script)

        # Update README
        logger.info('Updating README...')
        with open("README.md", "r", encoding='utf-8') as file:
            readme = file.read()

        start_index = readme.index('Data Last Updated: ')
        readme = readme[:start_index] + 'Data Last Updated: <strong>' + datetime.now().strftime("%B %d, %Y") + '</strong>\n</div>\n'

        with open("README.md", "w", encoding='utf-8') as file:
            file.write(readme)

        logger.info('\n✓ Update completed successfully!')

    except Exception as err:
        logger.error(f"Unexpected error: {err}", exc_info=True)
        raise


if __name__ == "__main__":
    main()
