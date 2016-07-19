"""
Downloads and converts files to various formats.
"""
import os
import re
from ftplib import FTP
import gzip
import requests
import subprocess

GENE_LIST_HOST = 'hgdownload.cse.ucsc.edu'
DOWNLOAD_CHUNK_SIZE = 16 * 1024


def download_and_convert(config, update_progress):
    """
    For each version of the genome in config download and convert genome, gene lists, and prediction files.
    :param config: Config: global configuration settings
    :param update_progress: func(str): called with messages related to progress
    """
    for genome_data in config.genome_data_list:
        genome_files = GenomeFiles(config, genome_data, update_progress)
        genome_files.download_genome()
        genome_files.download_gene_list_files()
        genome_files.download_prediction_files()


class GenomeFiles(object):
    """
    Provides functions for downloading and converting files for a version of genome specified via genome_data.
    """
    def __init__(self, config, genome_data, update_progress):
        """
        Setup for downloading/converting.
        :param config: Config: global configuration settings
        :param genome_data: dict: settings for a particular version of the genome
        :param update_progress: func(str): called with messages related to progress
        """
        self.config = config
        self.genome_data = genome_data
        self.update_progress = update_progress

    def download_genome(self):
        """
        Download a genome 2bit file.
        """
        downloader = GenomeDownloader(self.config.download_dir, GENE_LIST_HOST,
                                      self.genome_data.genome_file, self.genome_data.genomename,
                                      update_progress=self.update_progress)
        downloader.download()

    def download_gene_list_files(self):
        """
        Downloads and converts files related to gene lists specified in genome_data.
        """
        for target in self.genome_data.ftp_files:
            data_file = GeneListDownloader(self.config.download_dir, GENE_LIST_HOST, target,
                                           self.genome_data.genomename, update_progress=self.update_progress)
            data_file.download_and_extract()
            data_file.download_schema_and_convert()

    def download_prediction_files(self):
        """
        Downloads and converts prediction files for one version of the genome specified in genome_data.
        """
        for prediction_setting in self.genome_data.prediction_lists:
            downloader = PredictionDownloader(self.config, prediction_setting, update_progress=self.update_progress)
            downloader.download_and_convert()


class MySQLtoPG(object):
    """
    Converts MYSQL schema into a Postgres compatible one.
    Written specifically for UCSC MySQL schemas.
    """
    def __init__(self, schema_path, genome):
        self.schema_path = schema_path
        self.genome = genome

    def convert(self):
        """
        Converts schema_path from mysql to postgres format.
        :return:
        """
        converted_schema = ''
        with open(self.schema_path, 'r') as infile:
            for line in infile.readlines():
                if MySQLtoPG.include(line):
                    converted_schema += self.format(line)
        with open(self.schema_path, 'w') as outfile:
            outfile.write(converted_schema.replace(',\n) ;', '\n);'))

    @staticmethod
    def include(line):
        """
        Do we need to convert this line when converting the schema.
        :param line: str: line from mysql schema file.
        :return: bool: true if we need to include it
        """
        if line.startswith("--") or line.startswith('/*') or len(line.strip()) == 0 \
                or line.startswith("DROP") or line.startswith('  KEY'):
            return False
        return True

    def format(self, line):
        """
        Replace mysql data with postgres equivalents.
        :param line: str: line from mysql schema to convert to postgres format
        :return: str: formatted line
        """
        line = line.replace('`', '')
        line = line.replace('longblob', 'bytea')
        line = line.replace('ENGINE=MyISAM DEFAULT CHARSET=latin1', '')
        line = line.replace('int(10) unsigned', 'bigint')
        line = line.replace('int(11)', 'bigint')
        line = line.replace('smallint(5) unsigned', 'int')
        line = line.replace('CREATE TABLE ', 'CREATE TABLE ' + self.genome + '.')
        line = re.sub('enum\(.*\)', 'varchar', line)
        return line


class GenomeDownloader(object):
    """
    Retrieves 2bit genome file from via FTP.
    """
    def __init__(self, local_dir, ftp_host, ftp_path, genome, update_progress):
        self.local_dir = os.path.join(local_dir, genome)
        self.ftp_host = ftp_host
        self.ftp_path = ftp_path
        self.genome = genome
        self.update_progress = update_progress

    def download(self):
        """
        Download 2bit file via ftp.
        """
        self._download_file(self.get_ftp_filename(), self.get_local_path())

    def _download_file(self, filename, out_filename):
        """
        Download the specified file via ftp.
        :param filename: str: filename we should download via FTP
        :param out_filename: str: path where we should write the 2bit file.
        """
        self.update_progress('Downloading: ' + filename)
        if not os.path.exists(self.local_dir):
            os.mkdir(self.local_dir)
        ftp = FTP(self.ftp_host, 'anonymous', 'gcb-contact@duke.edu')
        ftp.cwd(self.get_ftp_dir())
        with open(out_filename, 'wb') as outfile:
            ftp.retrbinary("RETR " + filename, outfile.write)
        ftp.close()

    def get_ftp_dir(self):
        return os.path.dirname(self.ftp_path)

    def get_ftp_filename(self):
        return os.path.basename(self.ftp_path)

    def get_local_path(self):
        return os.path.join(self.local_dir, self.get_ftp_filename())

    def get_url(self):
        """
        Returns URL for documenting where the user can find this file via a browser.
        :return: URL equivalent for ftp file(UCSC keeps these in equivalent locations).
        """
        return "{}/{}".format(self.ftp_host, self.ftp_path)


class GeneListDownloader(object):
    """
    Fetches and converts a *.txt.gz file and accompanying *.sql(schema) from ftp server.
    """
    def __init__(self, local_dir, ftp_host, ftp_path, genome, update_progress):
        self.local_dir = os.path.join(local_dir, genome)
        self.ftp_host = ftp_host
        self.ftp_path = ftp_path
        self.genome = genome
        self.update_progress = update_progress

    def get_description(self):
        """
        Return user description for this file.
        """
        return "UCSC {} {}".format(self.genome, self.get_ftp_filename().replace(".txt.gz",""))

    def get_ftp_dir(self):
        return os.path.dirname(self.ftp_path)

    def get_ftp_filename(self):
        return os.path.basename(self.ftp_path)

    def get_local_path(self):
        return os.path.join(self.local_dir, self.get_ftp_filename())

    def get_root_filename(self):
        return re.sub(r".txt.gz$", "", self.get_ftp_filename())

    def get_ftp_schema_filename(self):
        return re.sub(r".txt.gz$", ".sql", self.get_ftp_filename())

    def get_local_schema_path(self):
        return os.path.join(self.local_dir, self.get_ftp_schema_filename())

    def get_extracted_path(self):
        extracted_filename = re.sub(r".txt.gz$", ".txt", self.get_ftp_filename())
        return os.path.join(self.local_dir, extracted_filename)

    def download_and_extract(self):
        self.update_progress('Downloading: ' + self.get_local_path())
        if not os.path.exists(self.local_dir):
            os.mkdir(self.local_dir)
        self._download_file(self.get_ftp_filename(), self.get_local_path())
        self.update_progress('Extracting: ' + self.get_local_path())
        self._extract()

    def _extract(self):
        local_path = self.get_local_path()
        dest_filename = self.get_extracted_path()
        with gzip.open(local_path, 'rb') as infile:
            with open(dest_filename, 'wb') as outfile:
                outfile.write(infile.read())

    def download_schema_and_convert(self):
        self.update_progress('Downloading: ' + self.get_ftp_schema_filename())
        self._download_file(self.get_ftp_schema_filename(), self.get_local_schema_path())
        self.update_progress('Fixing: ' + self.get_ftp_schema_filename())
        mysql_to_pg = MySQLtoPG(self.get_local_schema_path(), self.genome)
        mysql_to_pg.convert()

    def _download_file(self, filename, out_filename):
        ftp = FTP(self.ftp_host)
        ftp.login()
        ftp.cwd(self.get_ftp_dir())
        with open(out_filename, 'wb') as outfile:
            ftp.retrbinary("RETR " + filename, outfile.write)
        ftp.close()

    def get_url(self):
        """
        Returns URL for documenting where the user can find this file via a browser.
        :return: URL equivalent for ftp file(UCSC keeps these in equivalent locations).
        """
        return "{}/{}".format(self.ftp_host, self.ftp_path)


class PredictionDownloader(object):
    """
    Download a prediction file and convert into tsv format.
    """
    def __init__(self, config, prediction_settings, update_progress):
        """
        Setup to download the prediction file specified in prediction settings.
        :param config: pred.Config: global settings
        :param prediction_settings: object: details from config file for this prediction
        :param update_progress: func(str): called with messages related to progress
        """
        self.local_dir = config.download_dir
        self.name = prediction_settings.name
        self.url = prediction_settings.url
        self.genome = prediction_settings.genome
        self.update_progress = update_progress
        self.fix_script = prediction_settings.fix_script
        if not os.path.exists(self.local_dir):
            os.mkdir(self.local_dir)

    def get_url(self):
        return self.url

    def get_description(self):
        """
        Returns user description of this file.
        """
        return "Prediction {} {}".format(self.genome, self.name)

    def get_url_filename(self):
        return os.path.basename(self.url)

    def get_url_filename(self):
        return os.path.basename(self.url)

    def get_local_bigbed_path(self):
        return os.path.join(self.local_dir, self.genome, self.get_url_filename())

    def get_local_bed_path(self):
        pre, ext = os.path.splitext(self.get_url_filename())
        bed_filename = pre + '.bed'
        return os.path.join(self.local_dir, self.genome, bed_filename)

    def get_local_tsv_path(self):
        pre, ext = os.path.splitext(self.get_url_filename())
        bed_filename = pre + '.tsv'
        return os.path.join(self.local_dir, self.genome, bed_filename)

    def download_and_convert(self):
        """
        Downloads bigbed file and converts to tsv.
        :return:
        """
        local_filename = self.get_local_bigbed_path()
        self.update_progress('Downloading: ' + self.url)
        r = requests.get(self.url, stream=True)
        with open(local_filename, 'wb') as f:
            for chunk in r.iter_content(chunk_size=1024):
                if chunk: # filter out keep-alive new chunks
                    f.write(chunk)
        self.update_progress('Converting: ' + local_filename)
        ret = subprocess.call([self.fix_script, local_filename, self.get_local_bed_path()])
        if ret != 0:
            raise ValueError("Failed to convert dat a file:" + str(ret))
        self.create_tsv()

    def create_tsv(self):
        """
        Create tab separated file from bed file.
        """
        self.update_progress('Converting data source: ' + self.get_local_bed_path())
        temp_path = self.get_local_tsv_path()
        with open(self.get_local_bed_path(), 'r') as bedfile:
            with open(temp_path, 'w') as outfile:
                self.convert_tsv_data(bedfile, outfile)
                while True:
                    line = bedfile.readline()
                    if line:
                        parts = line.split('\t')
                        included_values = parts[:4]
                        (chorm, start_range, end_range, value) = included_values
                        result_values = [chorm, start_range, end_range, value, self.name, "[{},{}]".format(start_range, end_range)]
                        outfile.write('\t'.join(result_values) + '\n')
                    else:
                        break

    def convert_tsv_data(self, bed_file, outfile):
        """
        Convert lines from bed_file into tsv and write to outfile.
        :param bed_file: filehandle: we read lines from this file
        :param outfile: filehandle: we write lines to this file
        """
        while True:
            line = bed_file.readline()
            if line:
                parts = line.split('\t')
                included_values = parts[:4]
                (chrom, start_range, end_range, value) = included_values
                result_values = [chrom, start_range, end_range, value, self.name,
                                 "[{},{}]".format(start_range, end_range)]
                outfile.write('\t'.join(result_values) + '\n')
            else:
                break
