#!/usr/bin/env ruby
require 'json'
require 'psych'
GETTEXT_FUNC = "_i"
PATTERN = /(?<=#{GETTEXT_FUNC}\()(?:"|')(.+)(?:"|')/
LANG_NAME = '<lang_name>'
LANG_DIR = File.absolute_path(File.join(File.dirname(__FILE__), '../lang'))
LANG_FILE_EXT = '.json'
INITIAL_STRING = '=============='
def extract(file)
  result = {}
  file.each_line do |line|
    if PATTERN =~ line 
      result[$1] = INITIAL_STRING
    end
  end
  result
end


def check_unsed_msg(prev, current, name)
    unused_msgs = prev.keys - current.keys
    unless unused_msgs.empty?
        $stderr.puts "At #{name}:"
        unused_msgs.each do |msg|
            $stderr.puts "WARN: Message #{msg} is no longer used!"
        end
    end
end

extracted = extract(ARGF)
result = {}
Dir.glob(LANG_DIR + '/*').each do |path|
    prev = Psych.load_file(path)
    check_unsed_msg(prev, extracted, path)
    updated = extracted.dup.update(prev)
    localename = File.basename(path, LANG_FILE_EXT)
    File.write(path, JSON.pretty_generate(updated))
    result[localename] = updated
end

puts JSON.pretty_generate(result)

