from pyquery import PyQuery as pq
from time import sleep
import re
from csv import writer
import datetime
from translitua import translit, RussianSimple
import os
import urllib.request
import subprocess

SLEEP_TIME = 0.1
OUTPUT_FILE = 'candidates_archive_from_2012.csv'

SITE_FIRST_PART = "http://www.cvk.gov.ua/pls/"

ELECTION_INFO_SELECTOR = "tr td a.a6"
REGION_TITLE_SELECTOR_1 = "div#content table.t2:last"
REGION_TITLE_SELECTOR_2 = "tr td.td2 a.a1"
CANDIDATE_DISTRICT_SELECTOR_1 = "div#content table.t2:last"
CANDIDATE_DISTRICT_SELECTOR_2 = "tr td.td2 a.a1 b"
RESULTS_DISTRICT_SELECTOR_1 = "div#content table.t2:last"
RESULTS_DISTRICT_SELECTOR_2 = "tr td.td2 a.a1"
PARTY_SELECTOR_1 = "div#content table.t2"
PARTY_SELECTOR_2 = "tr td.td3 a.a1"
CANDIDATE_LIST_SELECTOR_1 = "div#content table.t2:last"
CANDIDATE_LIST_SELECTOR_2 = "tr td.td2 a.a1 b"
PARTY_RESULT_SELECTOR_1 = "div#content table.t2:last"
PARTY_RESULT_SELECTOR_2 = "tr td.td2 a.a1"
PARTY_MP_SELECTOR = "table.t2 tbody tr td.td3 a.a1"
PARTY_EX_MP_SELECTOR = "table.t2 tbody tr td.td3 a.a1"
PROGRAM_LINK_SELECTOR = "table.t2 tbody tr td.td2 a:last"

START_PAGE_TEMPLATE = "http://www.cvk.gov.ua/pls/{}/wp001"
ADD_START_PAGE_TEMPLATE = "http://www.cvk.gov.ua/pls/{}/WP001?PT001F01={}&rej=0"
REGIONS_TEMPLATE = "http://www.cvk.gov.ua/pls/{}/wp030?PT001F01={}"
DISTRICT_RESULTS_TEMPLATE = "http://www.cvk.gov.ua/pls/{}/WP040?PT001F01={}&pf7331={}"
DISTRICT_CANDIDATES_TEMPLATE = "http://www.cvk.gov.ua/pls/{}/WP033?PT001F01={}&pf7331={}"
PARTIES_LIST_TEMPLATE = "http://www.cvk.gov.ua/pls/{}/wp400?PT001F01={}"
PARTIES_RESULTS_TEMPLATE = "http://www.cvk.gov.ua/pls/{}/wp300?PT001F01={}"
PARTY_MPS_TEMPLATE = "http://www.cvk.gov.ua/pls/{}/WP602?PT001F01={}&pf7171={}&pf7331=0"
PARTY_EX_MPS_TEMPLATE = "http://www.cvk.gov.ua/pls/{}/WP603?PT001F01={}&pf7171={}&pf7331=0"
PARTY_RESULTS_LINK_TEMPLATE = "wp302?PT001F01={}&pf7171={}"
CANDIDATE_LIST_RESULT_TEMPLATE = "WP404?PT001F01={}&pf7201={}"


ELECTIONS_HREF_RE = re.compile("WP001\?PT001F01=(?P<election_id>\d+)&rej=0")
BIRTH_YEAR_RE = re.compile("(?P<birth_year>19.\d)")
CANDIDATE_HREF_RE = re.compile("WP407\?PT001F01=(?P<election_id>\d+)&pf7201=(?P<candidate_id>\d+)")
PARTY_LIST_RE = re.compile("WP502\?PT001F01=(?P<election_id>\d+)&pf7171=(?P<party_id>\d+)")

#PUNCT_RE = re.compile(

COUNCIL = "ВРУ"
COUNCIL_TYPE = "країна"
PLACE = "Україна"

METADATA_FIELDS = ['Author', 'Create Date', 'Last Modified By', 'Modify Date']
METADATA_TAGS = ['author', 'createdate', 'lastmodifiedby', 'modifydate']

OUTPUT_FOLDER = "programs/"

ROW_HEADERS = (
  'election', 'election_type', 'election_date',
  'council', 'council_type', 'convocation_number',
  'state', 'place','person_name', 'birth_year', 'nominated_by',
  'party_membership', 'candidate_type','list_number',
  'district_number', 'district_center', 'district_description',
  'result_binary', 'result_percents', 'comment',
  'person_id', 'convocation_id', 'district_id'
  ) + tuple(METADATA_FIELDS)

ELECTION_SWITCH = {
    'Відмінені вибори':'повторні',
    'Чергові вибори':'чергові',
    'Проміжні вибори':'проміжні',
    'Повторні вибори':'повторні',
    'Замість вибулих':'проміжні',
    'Позачергові вибори':'позачергові'
}

CVK_SITES = ["vnd2012" ,"vnd2014"]


def get_metadata(path, filename):
     metadata_dict = {}
     for i in range(len(METADATA_FIELDS)):
         try:
            command = ['exiftool', '-' + METADATA_TAGS[i], os.path.join(path, filename)]
            try:
                line = subprocess.check_output(command).decode('cp1251')
            except Exception:
                line = subprocess.check_output(command).decode('utf-8')
            #print(line)
            if ":" in line:
                try:
                    metadata_dict[METADATA_FIELDS[i]] = line.split(':', maxsplit = 1)[1].strip().encode('cp1251').decode('utf-8')
                except Exception: 
                    metadata_dict[METADATA_FIELDS[i]] = line.split(':', maxsplit = 1)
            else:
                metadata_dict[METADATA_FIELDS[i]] = line
         except Exception:
             metadata_dict[METADATA_FIELDS[i]] = ''
     return metadata_dict



def change_date_format(s):
  parts = s.split(".")
  return parts[2] + '-' + parts[1] + '-' + parts[0]

def party_find(s):
  ret = ''
  strs = s.split(", ")
  for part in strs:
    if ("член" in part and "парт".upper() in part.upper()) or ("безпарт" in part):
      ret = part
      break
  return ret


fh = open(OUTPUT_FILE,'w')
csvwriter = writer(fh)
csvwriter.writerow(ROW_HEADERS)


for el in range(2):
  start_page = pq(START_PAGE_TEMPLATE.format(CVK_SITES[el]))
  elect_ids = list()
  elect_types = list()
  elect_dates = list()
  elect_names = list()
  convocation_number = list()
  for elections in start_page(ELECTION_INFO_SELECTOR):
    print(pq(elections).text())
    elect_href_matched = ELECTIONS_HREF_RE.fullmatch(pq(elections).attr("href"))
    elect_ids.append(elect_href_matched.group("election_id"))
    elect_dates.append(change_date_format(pq(elections).text().split(" ",1)[0]))
    if datetime.datetime.strptime(elect_dates[-1], "%Y-%m-%d") >= datetime.datetime(2014, 10, 26, 0, 0):
      convocation_number.append("Верховна Рада 8")
      elect_names.append("Вибори до ВРУ 8 скликання (" + pq(elections).text().lower().replace(" вибори", "") + ")")
    else:
      convocation_number.append("Верховна Рада 7")
      elect_names.append("Вибори до ВРУ 7 скликання (" + pq(elections).text().lower().replace(" вибори", "") + ")")
    elect_types.append(ELECTION_SWITCH[pq(elections).text().split(" ",1)[1]])
  add_page = pq(ADD_START_PAGE_TEMPLATE.format(CVK_SITES[el], elect_ids[0]))
  print(ADD_START_PAGE_TEMPLATE.format(CVK_SITES[el], elect_ids[0]))
  for elections in add_page(ELECTION_INFO_SELECTOR):
    elect_href_matched = ELECTIONS_HREF_RE.fullmatch(pq(elections).attr("href"))
    print("Вибори до ВРУ 8 скликання (" + pq(elections).text().lower().replace(" вибори", "") + ")")
    if elect_href_matched.group("election_id") not in elect_ids:
      elect_ids.append(elect_href_matched.group("election_id"))
      elect_dates.append(change_date_format(pq(elections).text().split(" ",1)[0]))
      if datetime.datetime.strptime(elect_dates[-1], "%Y-%m-%d") >= datetime.datetime(2014, 10, 26, 0, 0):
        convocation_number.append("Верховна Рада 8")
        elect_names.append("Вибори до ВРУ 8 скликання (" + pq(elections).text().lower().replace(" вибори", "") + ")")
      else:
        convocation_number.append("Верховна Рада 7")
        elect_names.append("Вибори до ВРУ 7 скликання (" + pq(elections).text().lower().replace(" вибори", "") + ")")
      elect_types.append(ELECTION_SWITCH[pq(elections).text().split(" ",1)[1]])
  print(elect_names)
  print("Scrapping districts")
  for i in range(len(elect_ids)):
    print(elect_dates[i] + ", " + elect_types[i])
    regions_page = pq(REGIONS_TEMPLATE.format(CVK_SITES[el], elect_ids[i]))
    regions = regions_page(REGION_TITLE_SELECTOR_1)
    regions = regions(REGION_TITLE_SELECTOR_2)
    for region in regions:
      region_title = pq(region).text()
      region_districts = pq(region).parent().next().text()
      print(region_title)
      if "-" in region_districts:
        districts_str = region_districts.split("-")
        districts = range(int(districts_str[0]), int(districts_str[1])+1)
      elif "," in region_districts:
        districts_str = region_districts.split(", ")
        districts = list()
        for d in districts_str:
          districts.append(int(d))
      else:
        districts = [int(region_districts),]
      print(region_districts)
      for d in districts:
        print(d)
        candidates_page = pq(DISTRICT_CANDIDATES_TEMPLATE.format(CVK_SITES[el], elect_ids[i], str(d)))
        candidates = candidates_page(CANDIDATE_DISTRICT_SELECTOR_1)
        candidates = candidates(CANDIDATE_DISTRICT_SELECTOR_2)
        results_page = pq(DISTRICT_RESULTS_TEMPLATE.format(CVK_SITES[el], elect_ids[i], str(d)))
        no_results = False
        if "Неможливо встановити результат" in results_page.text():
          no_results = True
        results = results_page(RESULTS_DISTRICT_SELECTOR_1)
        results = results(RESULTS_DISTRICT_SELECTOR_2)
        for c in candidates:
          name = pq(c).text()
          nominated_by = pq(c).parent().parent().next().next().text()
          candidate_link = SITE_FIRST_PART + '/' + CVK_SITES[el] + '/' + pq(c).parent().attr('href')
          full_info = pq(c).parent().parent().next().text()
          party = party_find(full_info)
          birth_string = full_info.split(", ")[0]
          birth_year_matched = BIRTH_YEAR_RE.search(birth_string)
          birth_year = birth_year_matched.group('birth_year')
          candidate_href = pq(c).parent().attr("href")
          candidate_result_row = results_page('a.a1 [href = "' + candidate_href + '"]')
          percent = pq(candidate_result_row).parent().next().next().text()
          if no_results:
            result = "вибори недійсні"
          elif pq(results("a.a1:first")).attr("href") == candidate_href:
            result = "вибраний"
          else: 
            result = "не вибраний"
          program_file = translit(name.replace(" ","_")) + "_" + str(birth_year) + ".doc"  
          output_folder = OUTPUT_FOLDER + elect_dates[i] + '/'
          if not os.path.exists(output_folder):
              os.makedirs(output_folder)
          district_folder = output_folder + str(d) + '/'
          if not os.path.exists(district_folder):
              os.makedirs(district_folder)
          candidate_page = pq(candidate_link)
          program_link = SITE_FIRST_PART + '/' + CVK_SITES[el] + '/' + candidate_page(PROGRAM_LINK_SELECTOR).attr('href')
          if not os.path.exists(district_folder + program_file):
              urllib.request.urlretrieve(program_link, district_folder + program_file)
          metadata_dict = get_metadata(district_folder, program_file)
          print(metadata_dict)
          metadata_list = [metadata_dict[k] for k in METADATA_FIELDS ]

          output_row = [elect_names[i], elect_types[i], elect_dates[i], COUNCIL, COUNCIL_TYPE, convocation_number[i], "", PLACE, name, birth_year, nominated_by, party, "мажоритарний", "", d, "", "", result, percent, "", "", "", ""] + metadata_list
          
          csvwriter.writerow(output_row)        
        sleep(SLEEP_TIME)
  print("Scrapping lists")
  for i in range(len(elect_ids)):
    if elect_types[i] == "чергові" or elect_types[i] == "позачергові":
      parties_list_page = pq(PARTIES_LIST_TEMPLATE.format(CVK_SITES[el], elect_ids[i]))
      parties = parties_list_page(PARTY_SELECTOR_1)
      parties = parties(PARTY_SELECTOR_2)
      parties_results_page = pq(PARTIES_RESULTS_TEMPLATE.format(CVK_SITES[el], elect_ids[i]))
      parties_results = parties_results_page(PARTY_RESULT_SELECTOR_1)
      parties_results = parties_results(PARTY_RESULT_SELECTOR_2)
      for p in parties:
        nominated_by = pq(p).text()
        print(nominated_by)
        party_id_matched = PARTY_LIST_RE.fullmatch(pq(p).attr("href"))
        party_id = party_id_matched.group("party_id")
        
        party_list_page = pq(SITE_FIRST_PART + CVK_SITES[el] + '/' + pq(p).parent().next().children().attr("href"))
        party_href = PARTY_RESULTS_LINK_TEMPLATE.format(elect_ids[i], party_id)
        percent = parties_results('a.a1[href="' + party_href + '"]')
        #print(parties_results)
        percent = pq(percent).parent().next().next().text()
        party_id_matched = PARTY_LIST_RE.fullmatch(pq(p).attr("href"))
        party_id = party_id_matched.group("party_id")
        print(party_id)
        #print(PARTY_MPS_TEMPLATE.format(CVK_SITES[el], elect_ids[i], party_id))
        party_mps_page = pq(PARTY_MPS_TEMPLATE.format(CVK_SITES[el], elect_ids[i], party_id))
        party_mps = party_mps_page(PARTY_MP_SELECTOR)
        #print(party_mps_page)
        mps_href = list(map(lambda item:item.attr('href'), party_mps.items()))
        party_ex_mps_page = pq(PARTY_EX_MPS_TEMPLATE.format(CVK_SITES[el], elect_ids[i], party_id)) 
        party_ex_mps = party_ex_mps_page(PARTY_EX_MP_SELECTOR)
        ex_mps_href = list(map(lambda item:item.attr('href'), party_ex_mps.items()))
        #print(ex_mps_href)
        candidates = party_list_page(CANDIDATE_LIST_SELECTOR_1)
        #print(party_list_page)
        candidates = candidates(CANDIDATE_LIST_SELECTOR_2)
        for c in candidates:
          name = pq(c).text()
          full_info = pq(c).parent().parent().next().text()
          party = party_find(full_info)
          birth_string = full_info.split(", ")[0]
          birth_year_matched = BIRTH_YEAR_RE.search(birth_string)
          birth_year = birth_year_matched.group('birth_year')
          list_number = pq(c).parent().parent().prev().text()
          candidate_href = pq(c).parent().attr("href")
          cand_id_matched = CANDIDATE_HREF_RE.fullmatch(candidate_href)
          cand_id = cand_id_matched.group("candidate_id")
          candidate_results_href = CANDIDATE_LIST_RESULT_TEMPLATE.format(elect_ids[i], cand_id)
          if candidate_results_href in mps_href or candidate_results_href in ex_mps_href:
            result = "вибраний"
          else:
            result = "не вибраний"
          program_file = translit(name.replace(" ","_")) + "_" + str(birth_year) + ".doc"  
          output_folder = OUTPUT_FOLDER + elect_dates[i] + '/'
          if not os.path.exists(output_folder):
              os.makedirs(output_folder)
          party_folder = output_folder + elect_dates[i] + translit(nominated_by.replace(" ","_")) + '/'
          if not os.path.exists(party_folder):
              os.makedirs(party_folder)
          program_link = SITE_FIRST_PART + '/' + CVK_SITES[el] + '/' + candidate_page(PROGRAM_LINK_SELECTOR).attr('href')
          if not os.path.exists(party_folder + program_file):
              urllib.request.urlretrieve(program_link, party_folder + program_file)
          metadata_dict = get_metadata(party_folder, program_file)
          print(metadata_dict)
          metadata_list = [metadata_dict[k] for k in METADATA_FIELDS ]
          output_row = [elect_names[i], elect_types[i], elect_dates[i], COUNCIL, COUNCIL_TYPE, convocation_number[i], "", PLACE, name, birth_year,
          nominated_by, party, "список", list_number, "", "", "", result, percent, "", "", "", ""] + metadata_list
          csvwriter.writerow(output_row)
        sleep(SLEEP_TIME)
   
fh.close()
  