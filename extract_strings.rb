#!/usr/bin/env ruby
require 'json'

PATTERN = /(?<!_i\()\"(.+?)\"/
LANG_NAME = '<lang_name>'

def extract(file)
  result = {}
  file.each_line do |line|
    if PATTERN =~ line 
      result[$1] = ""
    end
  end
  { LANG_NAME => result }
end

puts JSON.pretty_generate(extract(ARGF))

